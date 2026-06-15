"""
Router Registry — SQLite-backed routing table.

Maps bot_id → agent_id → agent_url for proxy routing.
Also stores agent metadata (status, last_heartbeat).
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    agent_id       TEXT PRIMARY KEY,
    url            TEXT NOT NULL,
    access_key     TEXT NOT NULL DEFAULT '',
    status         TEXT NOT NULL DEFAULT 'online',
    last_heartbeat REAL NOT NULL DEFAULT 0,
    registered_at  REAL NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE TABLE IF NOT EXISTS bot_routes (
    bot_id    TEXT PRIMARY KEY,
    agent_id  TEXT NOT NULL REFERENCES agents(agent_id),
    routed_at REAL NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_bot_agent ON bot_routes(agent_id);
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
"""


class Registry:
    """Thread-safe routing table for bot → agent mapping."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    def start(self):
        self._init_db()

    def _init_db(self):
        if self._db_path is None:
            from conf.constants import SysVar
            self._db_path = str(Path(SysVar.ACCOUNT_PATH) / "router_registry.db")
        conn = self._get_conn()
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)
        conn.commit()
        logger.info("Registry started: %s", self._db_path)

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    # ── Agent CRUD ──────────────────────────────────────────────────────────

    def register_agent(self, agent_id: str, url: str, access_key: str = "") -> dict:
        """Register or update an agent. Idempotent."""
        now = time.time()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO agents (agent_id, url, access_key, status, last_heartbeat, registered_at)
                   VALUES (?, ?, ?, 'online', ?, ?)
                   ON CONFLICT(agent_id) DO UPDATE SET
                       url = excluded.url, access_key = excluded.access_key,
                       status = 'online', last_heartbeat = excluded.last_heartbeat""",
                (agent_id, url, access_key, now, now),
            )
            conn.commit()
        logger.info("Agent registered: %s → %s", agent_id, url)
        return self.get_agent(agent_id) or {}

    def unregister_agent(self, agent_id: str) -> bool:
        """Remove an agent and all its bot routes."""
        with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM bot_routes WHERE agent_id = ?", (agent_id,))
            c = conn.execute("DELETE FROM agents WHERE agent_id = ?", (agent_id,))
            conn.commit()
            return c.rowcount > 0

    def get_agent(self, agent_id: str) -> dict | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
        return dict(row) if row else None

    def list_agents(self) -> list[dict]:
        conn = self._get_conn()
        return [dict(r) for r in conn.execute("SELECT * FROM agents ORDER BY agent_id").fetchall()]

    def heartbeat(self, agent_id: str) -> bool:
        """Update agent heartbeat timestamp. Returns False if agent not found."""
        with self._lock:
            conn = self._get_conn()
            c = conn.execute(
                "UPDATE agents SET last_heartbeat = ?, status = 'online' WHERE agent_id = ?",
                (time.time(), agent_id),
            )
            conn.commit()
            return c.rowcount > 0

    def mark_offline(self, agent_id: str) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute("UPDATE agents SET status = 'offline' WHERE agent_id = ?", (agent_id,))
            conn.commit()

    # ── Bot Routing ─────────────────────────────────────────────────────────

    def route_bot(self, bot_id: str, agent_id: str) -> None:
        """Assign a bot to an agent."""
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO bot_routes (bot_id, agent_id, routed_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(bot_id) DO UPDATE SET agent_id = ?, routed_at = ?""",
                (bot_id, agent_id, time.time(), agent_id, time.time()),
            )
            conn.commit()

    def unroute_bot(self, bot_id: str) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM bot_routes WHERE bot_id = ?", (bot_id,))
            conn.commit()

    def resolve_bot(self, bot_id: str) -> dict | None:
        """Find which agent owns a bot. Returns {agent_id, url} or None."""
        conn = self._get_conn()
        row = conn.execute(
            """SELECT a.agent_id, a.url, a.status
               FROM bot_routes b JOIN agents a ON b.agent_id = a.agent_id
               WHERE b.bot_id = ?""",
            (bot_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_bot_routes(self, agent_id: str | None = None) -> list[dict]:
        conn = self._get_conn()
        if agent_id:
            rows = conn.execute(
                "SELECT * FROM bot_routes WHERE agent_id = ?", (agent_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM bot_routes ORDER BY agent_id").fetchall()
        return [dict(r) for r in rows]

    def get_agent_for_bot(self, bot_id: str) -> str | None:
        """Return agent_id that owns the bot, or None."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT agent_id FROM bot_routes WHERE bot_id = ?", (bot_id,),
        ).fetchone()
        return row[0] if row else None

    def pick_agent(self) -> dict | None:
        """Pick the online agent with fewest bots (for new bot placement)."""
        conn = self._get_conn()
        row = conn.execute(
            """SELECT a.agent_id, a.url, COUNT(b.bot_id) as bot_count
               FROM agents a LEFT JOIN bot_routes b ON a.agent_id = b.agent_id
               WHERE a.status = 'online'
               GROUP BY a.agent_id ORDER BY bot_count ASC LIMIT 1""",
        ).fetchone()
        return dict(row) if row else None


# Singleton
registry = Registry()
