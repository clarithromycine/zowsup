"""
Conversation Store — SQLite-backed conversation & message persistence.

Stores all E2E conversations and their messages for multi-bot management.
Thread-safe, with WAL mode for concurrent reads.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id              TEXT PRIMARY KEY,
    bot_id          TEXT NOT NULL,
    jid             TEXT NOT NULL,
    pn_jid          TEXT,
    notify_name     TEXT,
    type            TEXT NOT NULL DEFAULT '1v1',
    status          TEXT NOT NULL DEFAULT 'active',
    last_message_at REAL,
    last_message    TEXT,
    message_count   INTEGER NOT NULL DEFAULT 0,
    created_at      REAL NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at      REAL NOT NULL DEFAULT (strftime('%s', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_conv_bot ON conversations(bot_id);
CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(bot_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    msg_id          TEXT,
    direction       TEXT NOT NULL,
    content_type    TEXT NOT NULL,
    content         TEXT,
    participant_jid TEXT,
    status          TEXT NOT NULL DEFAULT 'EXECUTED',
    status_updated  REAL,
    raw             TEXT,
    sent_at         REAL NOT NULL,
    created_at      REAL NOT NULL DEFAULT (strftime('%s', 'now')),
    parent_id       INTEGER REFERENCES messages(id),
    note            TEXT,
    note_type       TEXT,
    media_url       TEXT,
    media_key       TEXT,
    media_mimetype  TEXT
);
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id, sent_at);
CREATE INDEX IF NOT EXISTS idx_msg_msgid ON messages(msg_id);
"""

_MIGRATIONS = [
    # Add pn_jid column for phone-number JID (auxiliary to LID-based canonical jid)
    "ALTER TABLE conversations ADD COLUMN pn_jid TEXT",
    "CREATE INDEX IF NOT EXISTS idx_conv_pn ON conversations(pn_jid)",
    # Add notify_name column for contact display name
    "ALTER TABLE conversations ADD COLUMN notify_name TEXT",
    "CREATE INDEX IF NOT EXISTS idx_conv_notify ON conversations(notify_name)",
    # Add media columns for IMAGE/VIDEO/AUDIO/DOCUMENT message support
    "ALTER TABLE messages ADD COLUMN parent_id INTEGER REFERENCES messages(id)",
    "ALTER TABLE messages ADD COLUMN note TEXT",
    "ALTER TABLE messages ADD COLUMN note_type TEXT",
    "ALTER TABLE messages ADD COLUMN media_url TEXT",
    "ALTER TABLE messages ADD COLUMN media_key TEXT",
    "ALTER TABLE messages ADD COLUMN media_mimetype TEXT",
    "ALTER TABLE messages ADD COLUMN media_file_name TEXT",
    "ALTER TABLE messages ADD COLUMN media_file_length INTEGER",
    "ALTER TABLE messages ADD COLUMN media_caption TEXT",
    # Add last_message for conversation list preview
    "ALTER TABLE conversations ADD COLUMN last_message TEXT",
    # Add avatar_id for cached contact avatar pictureId
    "ALTER TABLE conversations ADD COLUMN avatar_id TEXT",
]


class ConversationStore:
    """Thread-safe SQLite store for conversations and messages."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._initialized = False

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self):
        self._init_db()

    def _ensure_init(self):
        if not self._initialized:
            self._init_db()

    def _init_db(self):
        if self._db_path is None:
            from conf.constants import SysVar
            self._db_path = str(Path(SysVar.ACCOUNT_PATH) / "agent_conversations.db")
        conn = self._get_conn()
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)
        self._run_migrations(conn)
        conn.commit()
        self._initialized = True
        logger.info("ConversationStore started")

    def _run_migrations(self, conn: sqlite3.Connection):
        """Run schema migrations, ignoring errors for already-applied columns."""
        for sql in _MIGRATIONS:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass  # column already exists
            else:
                logger.debug("Migration applied: %s...", sql[:60])

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    # ── Conversations ────────────────────────────────────────────────────────

    def upsert_conversation(self, bot_id: str, jid: str, conv_type: str = "1v1",
                            pn_jid: str | None = None, notify_name: str | None = None) -> dict:
        """Get or create a conversation. Idempotent.

        Returns the conversation row as a dict.
        """
        self._ensure_init()
        conv_id = f"{bot_id}:{jid}"
        now = time.time()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO conversations (id, bot_id, jid, pn_jid, notify_name, type, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET pn_jid = COALESCE(excluded.pn_jid, pn_jid),
                                                 notify_name = COALESCE(excluded.notify_name, notify_name),
                                                 updated_at = ?""",
                (conv_id, bot_id, jid, pn_jid, notify_name, conv_type, now, now, now),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
        return dict(row)

    def resolve_conversation_jid(self, bot_id: str, query_jid: str) -> str | None:
        """Resolve a conversation ID from either canonical JID (LID) or pn_jid (phone).

        For PN (phone@s.whatsapp.net) queries, the LID-based conversation is
        always preferred.  This ensures PN and LID queries return the same
        conversation once an incoming message has established the LID mapping.

        Returns the conv_id if found, None otherwise.
        """
        self._ensure_init()
        conn = self._get_conn()

        # PN query: prefer LID-based conversation via pn_jid
        if query_jid.endswith("@s.whatsapp.net"):
            row = conn.execute(
                "SELECT id FROM conversations WHERE bot_id = ? AND pn_jid = ?",
                (bot_id, query_jid),
            ).fetchone()
            if row:
                return row[0]

        # Exact match (LID, group, or PN with no LID counterpart yet)
        conv_id = f"{bot_id}:{query_jid}"
        row = conn.execute("SELECT id FROM conversations WHERE id = ?", (conv_id,)).fetchone()
        return row[0] if row else None

    def get_conversation(self, conv_id: str) -> dict | None:
        """Return conversation summary (without messages)."""
        self._ensure_init()
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
        return dict(row) if row else None

    def list_conversations(self, bot_id: str | None = None) -> list[dict]:
        """List conversations, optionally filtered by bot_id. Ordered by updated_at DESC."""
        self._ensure_init()
        conn = self._get_conn()
        if bot_id:
            rows = conn.execute(
                "SELECT * FROM conversations WHERE bot_id = ? ORDER BY updated_at DESC", (bot_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM conversations ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]

    def update_notify_name(self, conv_id: str, name: str) -> None:
        """Update the contact display name for a conversation."""
        self._ensure_init()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "UPDATE conversations SET notify_name = ? WHERE id = ? AND (notify_name IS NULL OR notify_name != ?)",
                (name, conv_id, name),
            )
            conn.commit()

    def set_avatar_id(self, conv_id: str, avatar_id: str | None) -> None:
        """Update the cached avatar pictureId for a conversation.
        
        Set to None to invalidate the cache.
        """
        self._ensure_init()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "UPDATE conversations SET avatar_id = ? WHERE id = ?",
                (avatar_id, conv_id),
            )
            conn.commit()

    def find_conv_ids_by_jid(self, bot_id: str, jid: str) -> list[str]:
        """Find all conversation IDs that match a bot_id + jid (canonical or pn_jid).

        Supports matching across domain suffixes — e.g. a notification with
        ``248846345101511@lid`` will match a conversation stored as
        ``248846345101511@s.whatsapp.net``.
        """
        self._ensure_init()
        conn = self._get_conn()
        user_part = jid.split("@")[0] if "@" in jid else jid
        like_jid = f"{user_part}@%"
        rows = conn.execute(
            "SELECT id FROM conversations WHERE bot_id = ? AND (jid = ? OR pn_jid = ? OR jid LIKE ? OR pn_jid LIKE ?)",
            (bot_id, jid, jid, like_jid, like_jid),
        ).fetchall()
        return [r[0] for r in rows]

    def close_conversation(self, conv_id: str) -> bool:
        """Mark a conversation as closed."""
        self._ensure_init()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "UPDATE conversations SET status = 'closed', updated_at = ? WHERE id = ?",
                (time.time(), conv_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_conversation(self, conv_id: str) -> bool:
        """Delete a conversation and all its messages."""
        self._ensure_init()
        with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
            cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            conn.commit()
            return cursor.rowcount > 0

    def upgrade_conversation_jid(self, bot_id: str, msg_id: str, new_jid: str) -> bool:
        """Upgrade a PN-based conversation to LID-based when the server ACK
        reveals the recipient's LID.

        Finds the conversation that contains the given msg_id, and if its
        jid is a phone number (@s.whatsapp.net) while new_jid is a LID/g.us,
        renames the conversation accordingly.

        Returns True if the conversation was upgraded.
        """
        if new_jid.endswith("@s.whatsapp.net"):
            return False  # not a LID, nothing to upgrade
        self._ensure_init()
        with self._lock:
            conn = self._get_conn()
            # Find the message and its conversation
            row = conn.execute(
                "SELECT id, conversation_id FROM messages WHERE msg_id = ?",
                (msg_id,),
            ).fetchone()
            if not row:
                return False
            conv_id = row[1]
            # Check current jid
            conv = conn.execute(
                "SELECT jid FROM conversations WHERE id = ?", (conv_id,),
            ).fetchone()
            if not conv:
                return False
            old_jid = conv[0]
            if old_jid == new_jid:
                return False  # already correct
            if not old_jid.endswith("@s.whatsapp.net"):
                return False  # not a PN conversation, leave as-is

            new_conv_id = f"{bot_id}:{new_jid}"
            now = time.time()

            # Merge old PN conversation into new LID conversation
            conn.execute(
                "UPDATE messages SET conversation_id = ? WHERE conversation_id = ?",
                (new_conv_id, conv_id),
            )
            # Create or update the LID conversation metadata
            conn.execute(
                """INSERT INTO conversations (id, bot_id, jid, pn_jid, type, status,
                       message_count, last_message_at, created_at, updated_at)
                   SELECT ?, bot_id, ?, ?, type, status,
                       message_count, last_message_at, created_at, ?
                   FROM conversations WHERE id = ?
                   ON CONFLICT(id) DO UPDATE
                       SET message_count = message_count + excluded.message_count,
                           last_message_at = MAX(COALESCE(last_message_at, 0),
                               COALESCE(excluded.last_message_at, 0)),
                           updated_at = excluded.updated_at""",
                (new_conv_id, new_jid, old_jid, now, conv_id),
            )
            # Delete old PN conversation
            conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            conn.commit()

            logger.info("Upgraded conversation %s → %s", conv_id, new_conv_id)
            return True

    # ── Messages ─────────────────────────────────────────────────────────────

    @staticmethod
    def _merge_notes(msgs: list[dict]) -> list[dict]:
        """Merge note rows into their parent message using parent_id column."""
        # Build a map of parent_id → note content
        notes: dict[int, str] = {}
        for m in msgs:
            if m["direction"] == "note" and m.get("parent_id"):
                pid = m["parent_id"]
                if pid not in notes:
                    notes[pid] = m["content"]
        # Attach notes to their parent messages
        result = []
        for m in msgs:
            if m["direction"] == "note":
                continue
            pid = m.get("id")
            if pid in notes:
                m["note"] = notes[pid]
            result.append(m)
        return result

    def get_messages(
        self, conv_id: str, limit: int = 50,
        before: float | None = None,
        since: float | None = None,
    ) -> list[dict]:
        """Return messages for a conversation.

        Default: newest messages first (ORDER BY created_at DESC, LIMIT).
        since:  incremental poll — all messages with created_at > since,
                ordered ASC (oldest first) for easy append.
        before: pagination — messages with sent_at < before,
                ordered DESC (newest first).

        limit: max number of messages (default 50).
        """
        self._ensure_init()
        conn = self._get_conn()
        if since is not None:
            rows = conn.execute(
                """SELECT * FROM messages
                   WHERE conversation_id = ? AND created_at > ?
                   ORDER BY created_at ASC LIMIT ?""",
                (conv_id, since, limit),
            ).fetchall()
        elif before is not None:
            rows = conn.execute(
                """SELECT * FROM messages
                   WHERE conversation_id = ? AND sent_at < ?
                   ORDER BY sent_at DESC LIMIT ?""",
                (conv_id, before, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?",
                (conv_id, limit),
            ).fetchall()
        msgs = [dict(r) for r in rows]
        return msgs

    def record_message(
        self,
        conv_id: str,
        bot_id: str,
        jid: str,
        direction: str,
        content_type: str,
        content: str | None = None,
        msg_id: str | None = None,
        participant_jid: str | None = None,
        pn_jid: str | None = None,
        status: str | None = None,
        raw: str | None = None,
        sent_at: float | None = None,
        media_url: str | None = None,
        media_key: str | None = None,
        media_mimetype: str | None = None,
        media_file_name: str | None = None,
        media_file_length: int | None = None,
        media_caption: str | None = None,
        parent_id: int | None = None,
        note: str | None = None,
        note_type: str | None = None,
    ) -> dict:
        """Record a message and update conversation metadata.

        If the conversation does not exist, it is auto-created.

        status: message delivery state.  For incoming messages, pass None
                (no delivery tracking).  For outgoing, pass "EXECUTED".
                When tracking is active, update_message_status() updates it.

        Returns the message row as a dict.
        """
        self._ensure_init()
        if sent_at is None:
            sent_at = time.time()
        now = time.time()

        # Ensure conversation exists
        self.upsert_conversation(bot_id, jid, pn_jid=pn_jid)

        # Default status: None/"" for incoming (no delivery tracking),
        # "EXECUTED" for outgoing (delivery chain starts here).
        if status is None:
            status = "EXECUTED" if direction == "outgoing" else ""

        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                """INSERT INTO messages
                   (conversation_id, msg_id, direction, content_type, content,
                    participant_jid, status, raw, sent_at, created_at,
                    parent_id,
                    media_url, media_key, media_mimetype, media_file_name, media_file_length, media_caption,
                    note, note_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (conv_id, msg_id, direction, content_type, content,
                 participant_jid, status, raw, sent_at, now,
                 parent_id,
                 media_url, media_key, media_mimetype, media_file_name, media_file_length, media_caption,
                 note, note_type),
            )
            # Update conversation metadata (skip notes for message_count)
            if direction != "note":
                conn.execute(
                    """UPDATE conversations
                       SET message_count = message_count + 1,
                           last_message_at = ?,
                           last_message = ?,
                           updated_at = ?
                       WHERE id = ?""",
                    (sent_at, content, now, conv_id),
                )
            else:
                conn.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (now, conv_id),
                )
            conn.commit()
            row = conn.execute("SELECT * FROM messages WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(row)

    def update_message_note(self, message_db_id: int, note_content: str, note_type: str = "TRANSLATION") -> bool:
        """Update the note columns on an existing message."""
        self._ensure_init()
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "UPDATE messages SET note = ?, note_type = ? WHERE id = ?",
                (note_content, note_type, message_db_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_message_status(self, msg_id: str, status: str, sent_at=None) -> bool:
        """Update the delivery status of an outgoing message.

        When sent_at is provided (on SENT ack), the message's sent_at is
        also updated to reflect the actual server transmission time.
        """
        self._ensure_init()
        with self._lock:
            conn = self._get_conn()
            if sent_at is not None:
                cursor = conn.execute(
                    "UPDATE messages SET status = ?, status_updated = ?, sent_at = ? WHERE msg_id = ?",
                    (status, time.time(), sent_at, msg_id),
                )
            else:
                cursor = conn.execute(
                    "UPDATE messages SET status = ?, status_updated = ? WHERE msg_id = ?",
                    (status, time.time(), msg_id),
                )
            conn.commit()
            return cursor.rowcount > 0

    def get_message_by_msg_id(self, msg_id: str) -> dict | None:
        """Find a message by its WhatsApp message ID."""
        self._ensure_init()
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM messages WHERE msg_id = ?", (msg_id,)).fetchone()
        return dict(row) if row else None


# Singleton
conv_store = ConversationStore()
