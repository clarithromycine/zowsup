"""
Pydantic data models for the agent API.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Bot Status Enum ──────────────────────────────────────────────────────────

class BotStatus(str, Enum):
    """Runtime status of a bot."""
    INITIAL = "INITIAL"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"
    AUTH_FAILED = "AUTH_FAILED"


class BotEnv(str, Enum):
    """Device environment type."""
    ANDROID = "android"
    SMB_ANDROID = "smb_android"
    IOS = "ios"
    SMB_IOS = "smb_ios"


# ── Request Models ───────────────────────────────────────────────────────────

class BotStartRequest(BaseModel):
    """Request to start a single bot (used in batch)."""
    bot_id: str = Field(..., description="Phone number / bot identifier")
    env: Optional[BotEnv] = Field(None, description="Device environment (auto-detected from account config if omitted)")
    proxy: Optional[str] = Field(None, description="Proxy string, e.g. socks5://host:port")
    auto_login: bool = Field(True, description="Whether to auto-login on start")
    login_timeout: Optional[float] = Field(None, ge=5, le=300, description="Login wait timeout in seconds (5-300)")


class ListBotRequest(BaseModel):
    """Request to list bot statuses, optionally filtered by bot_ids."""
    bot_ids: list[str] | None = Field(None, description="Optional list of bot IDs to filter by. If omitted, returns all bots.")


class BatchStartRequest(BaseModel):
    """Request to start multiple bots at once.

    bots    — list of full BotStartRequest objects (env, proxy, auto_login per bot)
    bot_ids — list of plain bot_id strings (auto-detect env, default settings)
    mode    — "sync" (default, concurrent launch + wait for all logins) or "fire" (return immediately)
    """
    bots: list[BotStartRequest] = Field(default_factory=list, description="Full config per bot")
    bot_ids: list[str] = Field(default_factory=list, description="Plain bot IDs (auto-detect env)")
    mode: str = Field("sync", description="sync | fire")


class BatchStopRequest(BaseModel):
    """Request to stop multiple bots at once."""
    bot_ids: list[str] = Field(..., min_length=1, description="List of bot IDs to stop")
    mode: str = Field("graceful", description="graceful (wait for thread) | force (kill immediately)")


class PurgeRequest(BaseModel):
    """Request to purge (delete) one or more bot accounts.

    mode:
        "auto" — purge ALL accounts with status=auth_failed (ignores bot_ids).
        "list" — purge only the specified bot_ids that have status=auth_failed.
    """
    mode: str = Field("list", description="'auto' (all auth_failed) or 'list' (specific bot_ids)")
    bot_ids: list[str] = Field(default_factory=list, description="Bot IDs to purge (only used when mode='list')")


class PurgeResultEntry(BaseModel):
    """Result of purging a single account."""
    success: bool
    error: Optional[str] = None


class PurgeResponse(BaseModel):
    """Result of a purge operation."""
    results: dict[str, PurgeResultEntry]


class BotCmdRequest(BaseModel):
    """Request to execute a command on a running bot."""
    bot_id: str = Field(..., description="Bot identifier")
    command: str = Field(..., description="Command name, e.g. 'msg.send'")
    args: list[str] = Field(default_factory=list, description="Positional arguments")
    options: dict[str, Any] = Field(default_factory=dict, description="Keyword options")
    timeout: int = Field(30, ge=1, le=300, description="Timeout in seconds (1-300)")


class AdContent(BaseModel):
    """Ad message content for msg.sendad."""
    title: str = Field(..., description="Ad title")
    body: Optional[str] = Field(None, description="Ad title body text")
    url: str = Field(..., description="Ad URL / source URL")
    text: str = Field(..., description="Ad body text")
    thumbnailb64: Optional[str] = Field(None, description="Ad thumbnail image as base64 string")


class MediaContent(BaseModel):
    """Media message content for msg.sendmedia.

    Exactly one source must be provided: url, base64, or path.
    """
    type: str = Field(..., description="Media type: image | video | audio | document")
    url: Optional[str] = Field(None, description="HTTP/HTTPS URL of the media file")
    base64: Optional[str] = Field(None, description="Base64-encoded file content")
    path: Optional[str] = Field(None, description="Server-side file path")
    caption: Optional[str] = Field(None, description="Caption (image/video/audio)")
    fileName: Optional[str] = Field(None, description="Filename (document type only)")


class SendMsgContent(BaseModel):
    """Content for /api/sendmsg — exactly one field must be set."""
    text: Optional[str] = Field(None, description="Plain text message → msg.send")
    ad: Optional[AdContent] = Field(None, description="Ad message → msg.sendad")
    media: Optional[MediaContent] = Field(None, description="Media message → msg.sendmedia")


class SendMsgRequest(BaseModel):
    """High-level send message request."""
    bot_id: str = Field(..., description="Bot identifier")
    to: str = Field(..., description="Recipient JID, e.g. 8613800138000@s.whatsapp.net")
    content: SendMsgContent = Field(..., description="Message content (text or ad)")
    waitid: Optional[int] = Field(None, ge=1, le=300, description="If set, wait for message ID and return it (timeout in seconds)")


class BotImportRequestItem(BaseModel):
    """Single import data item."""
    data: str = Field(..., description="6-segment CSV: phone,pk1,sk1,pk2,sk2,sixth")
    env: BotEnv = Field(BotEnv.ANDROID, description="Device environment")


class BotImportRequest(BaseModel):
    """Request to import one or more bot accounts."""
    accounts: list[BotImportRequestItem] = Field(..., min_length=1, description="List of accounts to import")


class BotExportRequest(BaseModel):
    """Request to export one or more bot accounts."""
    bot_ids: list[str] = Field(..., min_length=1, description="List of bot IDs to export")


class BotExportEntry(BaseModel):
    """Single export result for one bot."""
    data: Optional[str] = Field(None, description="6-segment CSV export data")
    env: str = Field("", description="Device environment of the account")


# ── Response Models ──────────────────────────────────────────────────────────

class BotInfo(BaseModel):
    """Information about a running or stopped bot."""
    model_config = ConfigDict(exclude_none=True)

    bot_id: str
    status: BotStatus
    env: str = ""
    started_at: Optional[int] = None
    uptime_seconds: Optional[int] = None
    last_active: Optional[int] = None
    error: Optional[str] = None
    fail_reason: Optional[str] = None


class BatchResult(BaseModel):
    """Result of a batch start/stop operation."""
    results: list[BotInfo]
    success_count: int = 0
    error_count: int = 0


class CmdResult(BaseModel):
    """Result of a command execution. Extra fields from bot responses are passed through."""
    model_config = {"extra": "allow"}
    retcode: int = 0
    result: Optional[Any] = None
    error: Optional[str] = None


class LogLinesResponse(BaseModel):
    """Recent log lines for a bot."""
    bot_id: str
    lines: list[str]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str = ""
    uptime_seconds: int = 0
    thread_count: int = 0
    db_bot_count: int = 0
    running_bot_count: int = 0
    ws_connections: int = 0
    memory_bytes: int = 0
    cpu_time_seconds: float = 0.0


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str


# ── Conversation Models ──────────────────────────────────────────────────────

class ConversationType(str, Enum):
    ONE_TO_ONE = "1v1"
    GROUP = "group"


class ConversationInfo(BaseModel):
    """Summary of a conversation."""
    id: str
    bot_id: str
    jid: str
    pn_jid: Optional[str] = None
    notify_name: Optional[str] = None
    type: str = "1v1"
    status: str = "active"
    message_count: int = 0
    last_message_at: Optional[float] = None
    created_at: float = 0.0
    updated_at: float = 0.0


class MessageInfo(BaseModel):
    """A single message within a conversation."""
    id: int
    conversation_id: str
    msg_id: Optional[str] = None
    direction: str
    content_type: str = "TEXT"
    content: Optional[str] = None
    participant_jid: Optional[str] = None
    status: Optional[str] = None
    status_updated: Optional[float] = None
    sent_at: float = 0.0
    created_at: float = 0.0
    note: Optional[str] = None
    media_url: Optional[str] = None
    media_key: Optional[str] = None
    media_mimetype: Optional[str] = None
    media_file_name: Optional[str] = None
    media_file_length: Optional[int] = None
    media_caption: Optional[str] = None


class ConversationDetail(ConversationInfo):
    """Conversation with its messages."""
    messages: list[MessageInfo] = Field(default_factory=list)


class SendMessageRequest(BaseModel):
    """Request to send a message into a conversation."""
    content: str = Field(..., description="Message text or media description")
    content_type: str = Field("TEXT", description="MessageType enum value")
