"""
Escalation Queue — tracks conversations that need human attention.

When the AI plugin (or any plugin) returns an EscalateAction, it is
written here.  A human operator can then claim, reply, and resolve.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS escalation_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id          TEXT NOT NULL,
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
"""


class EscalationQueue:
    """Thread-safe escalation queue."""

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
        logger.info("EscalationQueue started")

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
    ) -> dict:
        """Add an escalation to the queue.  Idempotent."""
        self._ensure_init()
        now = time.time()
        with self._lock:
            conn = self._get_conn()
            # Idempotent: if same conv is already pending, update reason
            existing = conn.execute(
                "SELECT id FROM escalation_queue WHERE conversation_id = ? AND status = 'pending'",
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

            cursor = conn.execute(
                """INSERT INTO escalation_queue
                   (bot_id, conversation_id, reason, priority, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (bot_id, conversation_id, reason, priority, now, now),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM escalation_queue WHERE id = ?", (cursor.lastrowid,)).fetchone()
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

    def get(self, esc_id: int) -> dict | None:
        self._ensure_init()
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM escalation_queue WHERE id = ?", (esc_id,)).fetchone()
        return dict(row) if row else None

    def claim(self, esc_id: int, operator: str) -> bool:
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

    def resolve(self, esc_id: int) -> bool:
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

    def unclaim(self, esc_id: int) -> bool:
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


# Singleton
escalation_queue = EscalationQueue()
