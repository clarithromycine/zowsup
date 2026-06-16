"""
Audit Store — SQLite-backed HTTP API access log.

Thread-safe per-instance storage.  Each deployment mode (standalone agent,
cluster router) creates its own instance with a distinct DB name.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path

from conf.constants import SysVar

logger = logging.getLogger(__name__)

_MAX_ROWS = 100_000  # Auto-prune when exceeding this

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp  REAL    NOT NULL,
    method     TEXT    NOT NULL,
    path       TEXT    NOT NULL,
    source_ip  TEXT    NOT NULL DEFAULT '',
    bot_id     TEXT    NOT NULL DEFAULT '',
    status     INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_bot ON audit_log(bot_id);
CREATE INDEX IF NOT EXISTS idx_audit_path ON audit_log(path);
"""


class AuditStore:
    """Thread-safe audit log.  Create one instance per deployment role."""

    def __init__(self, db_name: str = "agent_audit.db"):
        self._db_name = db_name
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self):
        db_path = str(Path(getattr(SysVar, 'ACCOUNT_PATH', 'data/accounts')) / self._db_name)
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        for stmt in _SCHEMA.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(stmt)
        conn.commit()
        self._conn = conn
        logger.info("Audit store (%s) started at %s", self._db_name, db_path)

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.start()
        assert self._conn is not None
        return self._conn

    # ── Write ─────────────────────────────────────────────────────────────

    def record(self, method: str, path: str, source_ip: str,
               bot_id: str, status: int, duration_ms: int) -> None:
        """Insert an audit record. Thread-safe, fire-and-forget."""
        ts = time.time()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO audit_log (timestamp, method, path, source_ip, bot_id, status, duration_ms) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ts, method, path, source_ip, bot_id, status, duration_ms),
            )
            conn.commit()
            # Auto-prune
            count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
            if count > _MAX_ROWS:
                conn.execute(
                    "DELETE FROM audit_log WHERE id NOT IN (SELECT id FROM audit_log ORDER BY id DESC LIMIT ?)",
                    (_MAX_ROWS // 2,),
                )
                conn.commit()

    # ── Query ──────────────────────────────────────────────────────────────

    def query(self, *, limit: int = 200, bot_id: str | None = None,
              path_prefix: str | None = None, before_ts: float | None = None) -> list[dict]:
        """Return recent audit records, newest first."""
        conn = self._get_conn()
        sql = "SELECT * FROM audit_log WHERE 1=1"
        params: list = []
        if bot_id:
            sql += " AND bot_id = ?"
            params.append(bot_id)
        if path_prefix:
            sql += " AND path LIKE ?"
            params.append(path_prefix + "%")
        if before_ts:
            sql += " AND timestamp < ?"
            params.append(before_ts)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


# ── Module-level default instance ─────────────────────────────────────────────
# Set by server.py / cluster router after creating the appropriate instance.

_default_store: AuditStore | None = None


def set_default(store: AuditStore) -> None:
    global _default_store
    _default_store = store


def get_default() -> AuditStore:
    assert _default_store is not None, "AuditStore not started — call set_default() first"
    return _default_store
