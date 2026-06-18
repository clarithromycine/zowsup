"""
Plugin base classes and action types.

Plugins receive messages and API inputs, and return Actions that
control bot behavior or configuration.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ── Context ──────────────────────────────────────────────────────────────────

@dataclass
class MessageContext:
    """Incoming WhatsApp message passed to plugins."""

    bot_id: str
    jid: str                         # canonical LID (or group JID)
    pn_jid: str | None = None        # phone JID if available
    direction: str = ""              # "incoming" | "outgoing"
    content_type: str = "TEXT"       # e.g. "TEXT", "IMAGE"
    content: str | None = None
    message_id: str | None = None    # WhatsApp msg_id
    conversation_id: str = ""        # bot_id:jid
    participant_jid: str | None = None  # group participant
    db_id: int | None = None        # DB id of the stored message
    raw: dict | None = None          # original message dict
    stage: str = "normal"            # conversation stage (e.g. "surveying")



# ── Actions ──────────────────────────────────────────────────────────────────

class Action(ABC):
    """Base class for plugin output actions."""


@dataclass
class ReplyAction(Action):
    """Ask the bot to reply to a message."""
    conversation_id: str
    text: str
    target_lang: str = ""


@dataclass
class EscalateAction(Action):
    """Escalate a conversation to human review."""
    conversation_id: str
    reason: str = ""
    priority: str = "normal"         # "low" | "normal" | "high"


@dataclass
class NoAction(Action):
    """Plugin has no action to take."""


@dataclass
class ConfigAction(Action):
    """Plugin wants to change bot/agent configuration."""
    bot_id: str | None = None        # None = agent-level
    key: str = ""
    value: Any = None


# ── Plugin Base ──────────────────────────────────────────────────────────────

class Plugin(ABC):
    """Base class for all plugins.

    priority: execution order (lower = earlier).  Messages flow through
              plugins in ascending priority order.
    """

    name: str = ""
    version: str = "0.1.0"
    description: str = ""
    priority: int = 100

    async def on_start(self, bot_id: str) -> list[Action]:
        """Called when a bot starts.  Return actions to apply."""
        return []

    async def on_stop(self, bot_id: str) -> list[Action]:
        """Called when a bot stops."""
        return []

    async def on_message(self, ctx: MessageContext) -> list[Action]:
        """Called for every incoming message.
        
        Return one or more Actions.  PluginManager handles dispatch.
        """
        return [NoAction()]

    async def on_api_call(self, endpoint: str, data: dict, bot_id: str | None = None) -> list[Action]:
        """Called on relevant API calls.  Plugins can intercept/transform."""
        return []

    async def on_before_send(self, ctx: MessageContext) -> list[Action]:
        """Called just before a message is sent to WhatsApp.

        Plugins can transform the outgoing content (e.g. translation).
        Return a ReplyAction to override the send, or [] / NoAction to
        leave it unchanged.
        """
        return []
