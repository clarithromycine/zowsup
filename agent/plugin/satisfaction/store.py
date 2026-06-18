"""
Survey Session Store — SQLite-backed persistence for satisfaction surveys.

In standalone mode (no CLUSTER_URL): stores locally.
In cluster mode (CLUSTER_URL set): POSTs to Router's centralized survey store.
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
CREATE TABLE IF NOT EXISTS survey_sessions (
    id              TEXT PRIMARY KEY,
    bot_id          TEXT NOT NULL,
    agent_id        TEXT NOT NULL DEFAULT '',
    conversation_id TEXT NOT NULL,
    session_status  TEXT NOT NULL DEFAULT 'active',
    started_at      REAL NOT NULL DEFAULT (strftime('%s', 'now')),
    last_msg_at     REAL NOT NULL DEFAULT (strftime('%s', 'now')),
    survey_sent_at  REAL,
    rating          INTEGER,
    rating_at       REAL,
    ended_at        REAL,
    created_at      REAL NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at      REAL NOT NULL DEFAULT (strftime('%s', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_survey_conv ON survey_sessions(conversation_id);
CREATE INDEX IF NOT EXISTS idx_survey_bot ON survey_sessions(bot_id);
CREATE INDEX IF NOT EXISTS idx_survey_status ON survey_sessions(session_status);
"""


class SurveyStore:
    """Thread-safe survey session storage with optional cluster forwarding."""

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
            self._db_path = str(Path(SysVar.ACCOUNT_PATH) / "agent_surveys.db")
        conn = self._get_conn()
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)
        conn.commit()
        self._initialized = True
        logger.info("SurveyStore started: %s", self._db_path)

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def get_active_session(self, conversation_id: str) -> dict | None:
        """Return the current active/surveying session, or None.
        Only one active session per conversation at a time.
        """
        self._ensure_init()
        conn = self._get_conn()
        row = conn.execute(
            """SELECT * FROM survey_sessions
               WHERE conversation_id = ? AND session_status IN ('active', 'surveying')
               ORDER BY started_at DESC LIMIT 1""",
            (conversation_id,),
        ).fetchone()
        return dict(row) if row else None

    def create_session(self, bot_id: str, conversation_id: str,
                       agent_id: str = "", session_id: str = "") -> dict:
        """Create a new survey session.  Idempotent: if an active session
        already exists, returns the existing one.
        """
        self._ensure_init()
        existing = self.get_active_session(conversation_id)
        if existing:
            return existing

        sid = session_id or str(uuid.uuid4())
        now = time.time()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO survey_sessions
                   (id, bot_id, agent_id, conversation_id, started_at, last_msg_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (sid, bot_id, agent_id, conversation_id, now, now, now, now),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM survey_sessions WHERE id = ?", (sid,)).fetchone()
        logger.debug("Survey session created: %s for %s", sid, conversation_id)
        return dict(row)

    def touch_session(self, session_id: str) -> bool:
        """Update last_msg_at timestamp."""
        self._ensure_init()
        now = time.time()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "UPDATE survey_sessions SET last_msg_at = ?, updated_at = ? WHERE id = ?",
                (now, now, session_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def set_surveying(self, session_id: str) -> bool:
        """Mark session as surveying (survey question has been sent)."""
        self._ensure_init()
        now = time.time()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE survey_sessions
                   SET session_status = 'surveying', survey_sent_at = ?, updated_at = ?
                   WHERE id = ? AND session_status = 'active'""",
                (now, now, session_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def complete_survey(self, session_id: str, rating: int) -> bool:
        """Record a completed survey with rating (1-5)."""
        self._ensure_init()
        now = time.time()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE survey_sessions
                   SET session_status = 'completed', rating = ?, rating_at = ?,
                       ended_at = ?, updated_at = ?
                   WHERE id = ? AND session_status IN ('active', 'surveying')""",
                (rating, now, now, now, session_id),
            )
            conn.commit()
            if cursor.rowcount > 0:
                logger.info("Survey completed: %s rating=%d", session_id, rating)
            return cursor.rowcount > 0

    def expire_session(self, session_id: str) -> bool:
        """Mark session as expired (no rating given)."""
        self._ensure_init()
        now = time.time()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """UPDATE survey_sessions
                   SET session_status = 'expired', ended_at = ?, updated_at = ?
                   WHERE id = ? AND session_status IN ('active', 'surveying')""",
                (now, now, session_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get(self, session_id: str) -> dict | None:
        self._ensure_init()
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM survey_sessions WHERE id = ?", (session_id,)).fetchone()
        return dict(row) if row else None

    def list(self, bot_id: str | None = None, status: str | None = None,
             limit: int = 50) -> list[dict]:
        """List survey sessions, optionally filtered."""
        self._ensure_init()
        conn = self._get_conn()
        clauses = []
        params: list = []
        if bot_id:
            clauses.append("bot_id = ?")
            params.append(bot_id)
        if status:
            clauses.append("session_status = ?")
            params.append(status)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        rows = conn.execute(
            f"SELECT * FROM survey_sessions{where} ORDER BY started_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]


# Singleton
survey_store = SurveyStore()
