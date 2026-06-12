"""
Account Store — SQLite-backed account metadata management.

Stores bot_id, env, status, timestamps for all managed accounts.
Auto-discovers pre-existing accounts on first run (filesystem → DB migration).
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path

from conf.constants import SysVar

logger = logging.getLogger(__name__)

# DB file location — stored alongside accounts
_DB_NAME = "agent_accounts.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    bot_id      TEXT PRIMARY KEY,
    env         TEXT NOT NULL DEFAULT 'android',
    status      TEXT NOT NULL DEFAULT 'stopped',
    auth_detail TEXT,
    started_at  REAL,
    last_seen   REAL,
    created_at  REAL NOT NULL DEFAULT (strftime('%s', 'now'))
);
"""


class AccountStore:
    """Thread-safe SQLite store for bot account metadata."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path  # None means auto-detect in _init_db
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._initialized = False
        # Defer _init_db to first use — SysVar may not be loaded yet

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self):
        """Initialize the store. Called from agent lifespan."""
        self._init_db()

    def _ensure_init(self):
        if not self._initialized:
            self._init_db()

    def _init_db(self):
        if self._db_path is None:
            self._db_path = str(Path(SysVar.ACCOUNT_PATH) / _DB_NAME) if getattr(SysVar, 'ACCOUNT_PATH', None) else ":memory:"
        conn = self._get_conn()
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(_SCHEMA)
        # Schema migration: add auth_detail column if missing (pre-v2 DBs)
        self._migrate_add_column("auth_detail", "ALTER TABLE accounts ADD COLUMN auth_detail TEXT")
        conn.commit()
        self._initialized = True
        self._migrate_from_filesystem()

    def _migrate_add_column(self, col_name: str, ddl: str):
        """Idempotent column addition — checks if column exists first."""
        conn = self._get_conn()
        cursor = conn.execute("PRAGMA table_info(accounts)")
        existing = {row[1] for row in cursor.fetchall()}
        if col_name not in existing:
            conn.execute(ddl)
            logger.info(f"Schema migration: added column '{col_name}'")

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _migrate_from_filesystem(self):
        """One-time: scan ACCOUNT_PATH for existing accounts not yet in DB."""
        account_dir = Path(SysVar.ACCOUNT_PATH) if SysVar.ACCOUNT_PATH else None
        if not account_dir or not account_dir.exists():
            return

        conn = self._get_conn()
        existing = {r["bot_id"] for r in conn.execute("SELECT bot_id FROM accounts")}

        import re
        pattern = re.compile(r'^[\d_]+$')
        new_accounts = []
        for d in account_dir.iterdir():
            if d.is_dir() and pattern.match(d.name) and not d.name.startswith('_'):
                if d.name not in existing:
                    # Read env from config.json os_name field
                    env = self._read_env_from_config(d.name)
                    new_accounts.append((d.name, env))

        if new_accounts:
            now = int(time.time())
            with self._lock:
                conn.executemany(
                    "INSERT OR IGNORE INTO accounts (bot_id, env, created_at) VALUES (?, ?, ?)",
                    [(name, env, now) for name, env in new_accounts],
                )
                conn.commit()
            logger.info(f"Migrated {len(new_accounts)} existing accounts into agent DB")

        # Repair: update env for existing accounts that still have the SQLite default
        # (caused by a bug in the original migration that didn't read config.json)
        self._repair_env_defaults()

    def _read_env_from_config(self, bot_id: str) -> str:
        """Read the device environment from an account's config.json.

        Returns the env_name (e.g. 'smb_android') derived from config.os_name.
        Falls back to 'android' if the config cannot be read.
        """
        try:
            config_path = Path(SysVar.ACCOUNT_PATH) / bot_id / "config.json"
            if config_path.exists():
                import json
                with open(config_path, "r") as f:
                    config = json.load(f)
                os_name = config.get("os_name", "")
                # Map os_name back to env_name via SysVar.ENV_NAME_MAPPING
                from conf.constants import SysVar as _SysVar
                env = _SysVar.ENV_NAME_MAPPING.get(os_name, "")
                if env:
                    return env
        except Exception:
            pass
        return "android"

    def _repair_env_defaults(self):
        """One-time: fix accounts that were migrated with the SQLite default 'android'
        instead of the real env from config.json."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT bot_id FROM accounts WHERE env = 'android'"
        ).fetchall()
        if not rows:
            return

        repaired = 0
        for (bot_id,) in rows:
            real_env = self._read_env_from_config(bot_id)
            if real_env and real_env != "android":
                conn.execute("UPDATE accounts SET env = ? WHERE bot_id = ?", (real_env, bot_id))
                repaired += 1
        if repaired:
            conn.commit()
            logger.info(f"Repaired env for {repaired} accounts (default 'android' → actual)")

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def list_all(self) -> list[dict]:
        """Return all accounts with their metadata."""
        self._ensure_init()
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT bot_id, env, status, auth_detail, started_at, last_seen, created_at FROM accounts ORDER BY bot_id"
        ).fetchall()
        return [dict(r) for r in rows]

    def get(self, bot_id: str) -> dict | None:
        """Return metadata for one account, or None."""
        self._ensure_init()
        conn = self._get_conn()
        row = conn.execute(
            "SELECT bot_id, env, status, auth_detail, started_at, last_seen, created_at FROM accounts WHERE bot_id = ?",
            (bot_id,),
        ).fetchone()
        return dict(row) if row else None

    def exists(self, bot_id: str) -> bool:
        return self.get(bot_id) is not None

    def register(self, bot_id: str, env: str = "android") -> None:
        """Register a new account (INSERT only — never overwrites existing env)."""
        self._ensure_init()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT OR IGNORE INTO accounts (bot_id, env, status, created_at) VALUES (?, ?, 'stopped', ?)",
                (bot_id, env, int(time.time())),
            )
            conn.commit()
        logger.info(f"Account '{bot_id}' registered (env={env})")

    def update_status(self, bot_id: str, status: str, env: str | None = None, auth_detail: str | None = None) -> None:
        """Update running status. Optionally update env and/or auth_detail.

        When status is 'running', auth_detail is cleared (login succeeded).
        """
        self._ensure_init()
        now = int(time.time())
        with self._lock:
            conn = self._get_conn()
            if env is not None:
                conn.execute(
                    "UPDATE accounts SET status = ?, env = ?, last_seen = ? WHERE bot_id = ?",
                    (status, env, now, bot_id),
                )
            else:
                conn.execute(
                    "UPDATE accounts SET status = ?, last_seen = ? WHERE bot_id = ?",
                    (status, now, bot_id),
                )
            # auth_detail: explicitly set or clear on success
            if auth_detail is not None:
                conn.execute("UPDATE accounts SET auth_detail = ? WHERE bot_id = ?", (auth_detail, bot_id))
            elif status == "running":
                conn.execute("UPDATE accounts SET auth_detail = NULL WHERE bot_id = ?", (bot_id,))
            if status == "running":
                conn.execute(
                    "UPDATE accounts SET started_at = ? WHERE bot_id = ? AND started_at IS NULL",
                    (now, bot_id),
                )
            conn.commit()

    def list_by_status(self, status: str) -> list[dict]:
        """Return all accounts with a specific status."""
        self._ensure_init()
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT bot_id, env, status, auth_detail, started_at, last_seen, created_at FROM accounts WHERE status = ? ORDER BY bot_id",
            (status,),
        ).fetchall()
        return [dict(r) for r in rows]

    def update_last_seen(self, bot_id: str, timestamp: float | None = None) -> None:
        """Update only the last_seen timestamp without changing status.

        Used for lazy persistence: flush the runtime last_active cache to DB
        on bot stop or periodic timeout.
        """
        self._ensure_init()
        ts = int(timestamp) if timestamp is not None else int(time.time())
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "UPDATE accounts SET last_seen = ? WHERE bot_id = ?",
                (ts, bot_id),
            )
            conn.commit()

    def remove(self, bot_id: str) -> bool:
        """Remove an account from the store. Returns True if existed."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("DELETE FROM accounts WHERE bot_id = ?", (bot_id,))
            conn.commit()
            return cursor.rowcount > 0


# Singleton instance
account_store = AccountStore()
