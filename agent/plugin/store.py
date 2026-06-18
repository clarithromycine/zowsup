"""
Plugin configuration store — SQLite-backed, per-bot settings.

Schema:
  plugin_config (bot_id, plugin_name, enabled, config_json, updated_at)

An empty bot_id ('') represents the global default.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS plugin_config (
    bot_id      TEXT NOT NULL DEFAULT '',
    plugin_name TEXT NOT NULL,
    enabled     INTEGER NOT NULL DEFAULT 1,
    config_json TEXT NOT NULL DEFAULT '{}',
    updated_at  REAL NOT NULL DEFAULT (strftime('%s', 'now')),
    PRIMARY KEY (bot_id, plugin_name)
);
"""


class PluginStore:
    """Thread-safe plugin configuration store."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._initialized = False

    def start(self):
        self._init_db()

    def _ensure_init(self):
        if not self._initialized:
            self._init_db()

    def _init_db(self):
        if self._db_path is None:
            from conf.constants import SysVar
            self._db_path = str(Path(SysVar.ACCOUNT_PATH) / "plugin_config.db")
        conn = self._get_conn()
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)
        conn.commit()
        self._initialized = True
        logger.info("PluginStore started")

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def is_enabled(self, plugin_name: str, bot_id: str | None = None) -> bool:
        """Check if a plugin is enabled for a bot.

        Resolution order: bot-level → global default.
        """
        self._ensure_init()
        conn = self._get_conn()

        # Check bot-level first
        if bot_id:
            row = conn.execute(
                "SELECT enabled FROM plugin_config WHERE bot_id = ? AND plugin_name = ?",
                (bot_id, plugin_name),
            ).fetchone()
            if row is not None:
                return bool(row[0])

        # Fall back to global default
        row = conn.execute(
            "SELECT enabled FROM plugin_config WHERE bot_id = '' AND plugin_name = ?",
            (plugin_name,),
        ).fetchone()
        # No config at all → default to enabled
        return bool(row[0]) if row else True

    def set_enabled(self, plugin_name: str, enabled: bool, bot_id: str = "") -> None:
        """Enable or disable a plugin.  bot_id='' sets the global default."""
        self._ensure_init()
        now = time.time()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO plugin_config (bot_id, plugin_name, enabled, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(bot_id, plugin_name) DO UPDATE SET enabled = ?, updated_at = ?""",
                (bot_id, plugin_name, int(enabled), now, int(enabled), now),
            )
            conn.commit()

    def get_config(self, plugin_name: str, bot_id: str | None = None) -> dict:
        """Get plugin configuration, with bot-level override.

        Returns {} if no config exists.
        """
        self._ensure_init()
        conn = self._get_conn()
        config = {}

        # Global default
        row = conn.execute(
            "SELECT config_json FROM plugin_config WHERE bot_id = '' AND plugin_name = ?",
            (plugin_name,),
        ).fetchone()
        if row:
            config.update(json.loads(row[0]))

        # Bot-level override
        if bot_id:
            row = conn.execute(
                "SELECT config_json FROM plugin_config WHERE bot_id = ? AND plugin_name = ?",
                (bot_id, plugin_name),
            ).fetchone()
            if row:
                config.update(json.loads(row[0]))

        return config

    def set_config(self, plugin_name: str, config: dict, bot_id: str = "") -> None:
        """Set plugin configuration.  Merges with existing config."""
        self._ensure_init()
        now = time.time()
        existing = self.get_config(plugin_name, bot_id if bot_id else None)
        existing.update(config)
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO plugin_config (bot_id, plugin_name, config_json, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(bot_id, plugin_name) DO UPDATE SET config_json = ?, updated_at = ?""",
                (bot_id, plugin_name, json.dumps(existing), now,
                 json.dumps(existing), now),
            )
            conn.commit()

    def export_all(self) -> list[dict]:
        """Export all plugin configs (for syncing to agents)."""
        self._ensure_init()
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM plugin_config").fetchall()
        return [dict(r) for r in rows]

    def import_from(self, rows: list[dict]) -> None:
        """Bulk-import plugin configs from a central store."""
        self._ensure_init()
        now = time.time()
        with self._lock:
            conn = self._get_conn()
            for r in rows:
                conn.execute(
                    """INSERT INTO plugin_config (bot_id, plugin_name, enabled, config_json, updated_at)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(bot_id, plugin_name) DO UPDATE SET
                           enabled = excluded.enabled,
                           config_json = excluded.config_json,
                           updated_at = excluded.updated_at""",
                    (r["bot_id"], r["plugin_name"], r["enabled"], r["config_json"], now),
                )
            conn.commit()

    def list_plugins(self, bot_id: str | None = None) -> list[dict]:
        """List plugin states for a bot or globally."""
        self._ensure_init()
        conn = self._get_conn()
        if bot_id:
            rows = conn.execute(
                "SELECT * FROM plugin_config WHERE bot_id = ?", (bot_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM plugin_config WHERE bot_id = ''",
            ).fetchall()
        return [dict(r) for r in rows]


def inner_config(cfg: dict) -> dict:
    """Extract the inner config values from a plugin config dict.
    Handles both wrapper format {"plugin":...,"config":{...}} and raw format.
    """
    if isinstance(cfg, dict) and isinstance(cfg.get("config"), dict):
        return cfg["config"]
    return cfg


# Singleton
plugin_store = PluginStore()


def get_cluster_plugin_store() -> PluginStore:
    """Get or create the Router's centralized plugin config store."""
    from pathlib import Path as _Path
    import os as _os
    try:
        from conf.constants import SysVar
        db_path = str(_Path(SysVar.ACCOUNT_PATH) / "cluster_plugin_config.db")
    except Exception:
        here = str(_Path(_os.path.dirname(_os.path.abspath(__file__))))
        base = here.rsplit("/agent", 1)[0]
        db_path = f"{base}/data/accounts/cluster_plugin_config.db"
    _Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    s = PluginStore(db_path)
    s._ensure_init()
    return s
