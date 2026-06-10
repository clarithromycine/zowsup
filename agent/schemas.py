"""
Pydantic data models for the agent API.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Bot Status Enum ──────────────────────────────────────────────────────────

class BotStatus(str, Enum):
    """Runtime status of a bot."""
    INITIAL = "INITIAL"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


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


class BatchStartRequest(BaseModel):
    """Request to start multiple bots at once.

    bots    — list of full BotStartRequest objects (env, proxy, auto_login per bot)
    bot_ids — list of plain bot_id strings (auto-detect env, default settings)
    """
    bots: list[BotStartRequest] = Field(default_factory=list, description="Full config per bot")
    bot_ids: list[str] = Field(default_factory=list, description="Plain bot IDs (auto-detect env)")


class BatchStopRequest(BaseModel):
    """Request to stop multiple bots at once."""
    bot_ids: list[str] = Field(..., min_length=1, description="List of bot IDs to stop")


class BotCmdRequest(BaseModel):
    """Request to execute a command on a running bot."""
    bot_id: str = Field(..., description="Bot identifier")
    command: str = Field(..., description="Command name, e.g. 'msg.send'")
    args: list[str] = Field(default_factory=list, description="Positional arguments")
    options: dict[str, Any] = Field(default_factory=dict, description="Keyword options")
    timeout: int = Field(30, ge=1, le=300, description="Timeout in seconds (1-300)")


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
    bot_id: str
    status: BotStatus
    env: str = ""
    started_at: Optional[int] = None
    uptime_seconds: Optional[int] = None
    error: Optional[str] = None


class BatchResult(BaseModel):
    """Result of a batch start/stop operation."""
    results: list[BotInfo]
    success_count: int = 0
    error_count: int = 0


class CmdResult(BaseModel):
    """Result of a command execution."""
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


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
