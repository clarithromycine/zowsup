"""
Plugin Manager — loads, configures, and dispatches plugins.

Registered plugins receive on_message / on_start / on_stop events.
The manager respects per-bot enable/disable settings via PluginStore.
"""

from __future__ import annotations

import logging
from typing import Type

from agent.plugin import Plugin, MessageContext, Action, NoAction, ReplyAction
from agent.plugin.store import plugin_store

logger = logging.getLogger(__name__)


class PluginManager:
    """Singleton registry and dispatcher for plugins."""

    def __init__(self):
        self._plugins: dict[str, Plugin] = {}

    # ── Registration ─────────────────────────────────────────────────────────

    def register(self, plugin: Plugin) -> None:
        """Register a plugin instance."""
        if plugin.name in self._plugins:
            logger.warning("Plugin '%s' already registered, replacing", plugin.name)
        self._plugins[plugin.name] = plugin
        logger.info("Plugin registered: %s v%s", plugin.name, plugin.version)

    def unregister(self, name: str) -> None:
        self._plugins.pop(name, None)

    @property
    def names(self) -> list[str]:
        return list(self._plugins.keys())

    def get(self, name: str) -> Plugin | None:
        return self._plugins.get(name)

    # ── Dispatch ─────────────────────────────────────────────────────────────

    def _sorted_plugins(self):
        """Yield (name, plugin) pairs in ascending priority order."""
        return sorted(self._plugins.items(), key=lambda item: item[1].priority)

    async def dispatch_on_message(self, ctx: MessageContext) -> list[Action]:
        """Dispatch incoming message to all enabled plugins.  Skips disabled."""
        actions: list[Action] = []
        for name, plugin in self._sorted_plugins():
            if not plugin_store.is_enabled(name, ctx.bot_id):
                continue
            try:
                result = await plugin.on_message(ctx)
                actions.extend(result)
            except Exception:
                logger.exception("Plugin '%s' on_message failed", name)
        return actions

    async def dispatch_on_start(self, bot_id: str) -> list[Action]:
        """Notify plugins that a bot has started."""
        actions: list[Action] = []
        for name, plugin in self._sorted_plugins():
            if not plugin_store.is_enabled(name, bot_id):
                continue
            try:
                result = await plugin.on_start(bot_id)
                actions.extend(result)
            except Exception:
                logger.exception("Plugin '%s' on_start failed for bot '%s'", name, bot_id)
        return actions

    async def dispatch_on_stop(self, bot_id: str) -> list[Action]:
        """Notify plugins that a bot has stopped."""
        actions: list[Action] = []
        for name, plugin in self._sorted_plugins():
            if not plugin_store.is_enabled(name, bot_id):
                continue
            try:
                result = await plugin.on_stop(bot_id)
                actions.extend(result)
            except Exception:
                logger.exception("Plugin '%s' on_stop failed for bot '%s'", name, bot_id)
        return actions

    async def dispatch_on_before_send(self, ctx: MessageContext) -> list[Action]:
        """Notify plugins just before a message is sent to WhatsApp.

        Plugins can return a ReplyAction to override the outgoing content.
        The first ReplyAction wins; subsequent ones are ignored.
        """
        actions: list[Action] = []
        for name, plugin in self._sorted_plugins():
            if not plugin_store.is_enabled(name, ctx.bot_id):
                continue
            try:
                result = await plugin.on_before_send(ctx)
                actions.extend(result)
            except Exception:
                logger.exception("Plugin '%s' on_before_send failed", name)
        return actions

    async def execute_actions(self, actions: list[Action]) -> None:
        """Execute the actions returned by plugins.

        ReplyAction  → sends a WhatsApp message via the bot.
        Other actions → logged for upstream handling.
        """
        import asyncio
        from agent.manager.bot_manager import bot_manager

        for action in actions:
            if isinstance(action, ReplyAction):
                conv_id = action.conversation_id
                parts = conv_id.split(":", 1)
                if len(parts) != 2:
                    continue
                bot_id, jid = parts

                if bot_manager.get_bot_instance(bot_id) is None:
                    logger.warning("Bot '%s' not running, skipping reply", bot_id)
                    continue

                try:
                    await asyncio.to_thread(
                        bot_manager.execute_cmd,
                        bot_id=bot_id,
                        cmd_name="msg.send",
                        args=[jid, action.text],
                        timeout=30,
                    )
                    logger.info("Plugin reply sent to %s: %s", conv_id, action.text[:50])
                except Exception:
                    logger.exception("Failed to send plugin reply for bot '%s'", bot_id)

            elif isinstance(action, EscalateAction):
                from agent.manager.escalation_queue import escalation_queue
                parts = action.conversation_id.split(":", 1)
                esc_bot_id = parts[0] if len(parts) >= 1 else "unknown"
                escalation_queue.add(
                    bot_id=esc_bot_id,
                    conversation_id=action.conversation_id,
                    reason=action.reason,
                    priority=action.priority,
                )
                logger.info(
                    "Escalated: %s (reason=%s, priority=%s)",
                    action.conversation_id, action.reason, action.priority,
                )

            elif isinstance(action, ConfigAction):
                logger.info("ConfigAction: %s = %s", action.key, action.value)


# Singleton
plugin_manager = PluginManager()
