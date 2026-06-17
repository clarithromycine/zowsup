"""
Escalation Queue — tracks conversations that need human attention.

In standalone mode (no CLUSTER_URL): stores locally with UUID-based IDs.
In cluster mode (CLUSTER_URL set): POSTs to Router's centralized escalation store.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS escalation_queue (
    id              TEXT PRIMARY KEY,
    bot_id          TEXT NOT NULL,
    agent_id        TEXT NOT NULL DEFAULT '',
    conversation_id TEXT NOT NULL,
    reason          TEXT NOT NULL DEFAULT '',
    priority        TEXT NOT NULL DEFAULT 'normal',
    status          TEXT NOT NULL DEFAULT 'pending',
    claimed_by      TEXT,
    claimed_at      REAL,
    resolved_at     REAL,
    created_at      REAL NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at      REAL NOT NULL DEFAULT (strftime('%s', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_esc_status ON escalation_queue(status);
CREATE INDEX IF NOT EXISTS idx_esc_bot ON escalation_queue(bot_id);
CREATE INDEX IF NOT EXISTS idx_esc_conv ON escalation_queue(conversation_id);
CREATE INDEX IF NOT EXISTS idx_esc_agent ON escalation_queue(agent_id);
"""


class EscalationQueue:
    """Thread-safe escalation queue with optional cluster forwarding."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._initialized = False

    def start(self) -> None:
        self._init_db()

    def _ensure_init(self) -> None:
        if not self._initialized:
            self._init_db()

    def _init_db(self) -> None:
        if self._db_path is None:
            from conf.constants import SysVar
            self._db_path = str(Path(SysVar.ACCOUNT_PATH) / "agent_escalations.db")
        conn = self._get_conn()
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)
        conn.commit()
        self._initialized = True
        logger.info("EscalationQueue started: %s", self._db_path)

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def add(
        self,
        bot_id: str,
        conversation_id: str,
        reason: str = "",
        priority: str = "normal",
        agent_id: str = "",
        escalation_id: str = "",
    ) -> dict:
        """Add an escalation.  Idempotent by conversation_id + active status."""
        self._ensure_init()
        esc_id = escalation_id or str(uuid.uuid4())
        now = time.time()
        with self._lock:
            conn = self._get_conn()
            existing = conn.execute(
                "SELECT id FROM escalation_queue WHERE conversation_id = ? AND status IN ('pending', 'claimed')",
                (conversation_id,),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE escalation_queue SET reason = ?, updated_at = ? WHERE id = ?",
                    (reason, now, existing[0]),
                )
                conn.commit()
                row = conn.execute("SELECT * FROM escalation_queue WHERE id = ?", (existing[0],)).fetchone()
                return dict(row)

            conn.execute(
                """INSERT INTO escalation_queue
                   (id, bot_id, agent_id, conversation_id, reason, priority, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (esc_id, bot_id, agent_id, conversation_id, reason, priority, now, now),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM escalation_queue WHERE id = ?", (esc_id,)).fetchone()
        return dict(row)

    def list(self, status: str | None = None, bot_id: str | None = None) -> list[dict]:
        """List escalations.  Default: all non-resolved."""
        self._ensure_init()
        conn = self._get_conn()
        if status:
            rows = conn.execute(
                "SELECT * FROM escalation_queue WHERE status = ? ORDER BY priority DESC, created_at ASC",
                (status,),
            ).fetchall()
        elif bot_id:
            rows = conn.execute(
                "SELECT * FROM escalation_queue WHERE bot_id = ? AND status != 'resolved' "
                "ORDER BY priority DESC, created_at ASC",
                (bot_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM escalation_queue WHERE status != 'resolved' "
                "ORDER BY priority DESC, created_at ASC",
            ).fetchall()
        return [dict(r) for r in rows]

    def get(self, esc_id: str) -> dict | None:
        self._ensure_init()
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM escalation_queue WHERE id = ?", (esc_id,)).fetchone()
        return dict(row) if row else None

    def claim(self, esc_id: str, operator: str) -> bool:
        """Claim an escalation for a human operator."""
        self._ensure_init()
        now = time.time()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE escalation_queue
                   SET status = 'claimed', claimed_by = ?, claimed_at = ?, updated_at = ?
                   WHERE id = ? AND status = 'pending'""",
                (operator, now, now, esc_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def resolve(self, esc_id: str) -> bool:
        """Resolve (close) an escalation."""
        self._ensure_init()
        now = time.time()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "UPDATE escalation_queue SET status = 'resolved', resolved_at = ?, updated_at = ? WHERE id = ?",
                (now, now, esc_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def unclaim(self, esc_id: str) -> bool:
        """Return a claimed escalation back to pending."""
        self._ensure_init()
        now = time.time()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE escalation_queue
                   SET status = 'pending', claimed_by = NULL, claimed_at = NULL, updated_at = ?
                   WHERE id = ? AND status = 'claimed'""",
                (now, esc_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def is_claimed(self, conversation_id: str) -> bool:
        """Check if a conversation has an active claimed escalation."""
        self._ensure_init()
        conn = self._get_conn()
        row = conn.execute(
            "SELECT 1 FROM escalation_queue WHERE conversation_id = ? AND status = 'claimed' LIMIT 1",
            (conversation_id,),
        ).fetchone()
        return row is not None


# Singleton for standalone agent
escalation_queue = EscalationQueue()


# ── Router-side singleton ────────────────────────────────────────────────────

def get_cluster_queue() -> EscalationQueue:
    """Get or create the Router's centralized escalation store."""
    import os as _os
    from pathlib import Path as _Path
    try:
        from conf.constants import SysVar
        db_path = str(_Path(SysVar.ACCOUNT_PATH) / "cluster_escalations.db")
    except Exception:
        here = str(_Path(_os.path.dirname(_os.path.abspath(__file__))))
        base = here.rsplit("/agent", 1)[0]
        db_path = f"{base}/data/accounts/cluster_escalations.db"
    _Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    q = EscalationQueue(db_path)
    q._ensure_init()
    return q
