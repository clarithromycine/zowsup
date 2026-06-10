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
    command: str = Field(..., description="Command name, e.g. 'msg.send'")
    args: list[str] = Field(default_factory=list, description="Positional arguments")
    options: dict[str, Any] = Field(default_factory=dict, description="Keyword options")
    timeout: int = Field(30, ge=1, le=300, description="Timeout in seconds (1-300)")


class ScriptRunRequest(BaseModel):
    """Request to run a script."""
    args: list[str] = Field(default_factory=list, description="Script arguments")
    timeout: int = Field(30, ge=1, le=600, description="Timeout in seconds (1-600)")


class BotImportRequest(BaseModel):
    """Request to import a bot account (import6 6-segment CSV format)."""
    data: str = Field(..., description="6-segment CSV: phone,pk1,sk1,pk2,sk2,sixth")
    bot_id: Optional[str] = Field(None, description="Bot ID override (extracted from data if omitted)")
    env: BotEnv = Field(BotEnv.ANDROID, description="Device environment for import")


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


class ScriptResult(BaseModel):
    """Result of a script execution."""
    retcode: int = 0
    stdout: str = ""
    stderr: str = ""


class ScriptInfo(BaseModel):
    """Metadata for an available script."""
    name: str
    description: str = ""


class ScriptListResponse(BaseModel):
    """List of available scripts."""
    scripts: list[ScriptInfo]


class LogLinesResponse(BaseModel):
    """Recent log lines for a bot."""
    bot_id: str
    lines: list[str]


class BotEventMessage(BaseModel):
    """Structured bot event pushed over WebSocket."""
    type: str  # "event", "message", "message_status", "cmd_result"
    bot_id: str
    data: dict[str, Any]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
