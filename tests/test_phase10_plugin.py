"""Phase 10: Plugin — Store CRUD and Manager dispatch tests.

Covers:
- PluginStore: enable/disable (global + per-bot), get_config/set_config merge,
  export_all, import_from
- PluginManager: register, dispatch_on_message → ReplyAction / EscalateAction /
  TranslateAction
"""

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# PluginStore unit tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPluginStore:
    """Unit tests for PluginStore (SQLite in-memory)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from agent.plugin.store import PluginStore
        self.store = PluginStore(":memory:")
        self.store.start()

    # ── Enable / Disable ─────────────────────────────────────────────────────

    def test_default_enabled_when_no_config(self):
        """Plugin with no config defaults to enabled."""
        assert self.store.is_enabled("ai") is True
        assert self.store.is_enabled("translation") is True

    def test_disable_enable_global(self):
        self.store.set_enabled("ai", False)
        assert self.store.is_enabled("ai") is False
        self.store.set_enabled("ai", True)
        assert self.store.is_enabled("ai") is True

    def test_disable_enable_per_bot_override(self):
        """Bot-level setting overrides global."""
        self.store.set_enabled("ai", False)  # global off
        self.store.set_enabled("ai", True, bot_id="bot-1")  # bot-1 on
        assert self.store.is_enabled("ai") is False          # global still off
        assert self.store.is_enabled("ai", bot_id="bot-1") is True  # bot override

    def test_disable_per_bot_only(self):
        """Disable plugin for one bot, not globally."""
        self.store.set_enabled("ai", False, bot_id="bot-special")
        assert self.store.is_enabled("ai") is True           # global still on
        assert self.store.is_enabled("ai", bot_id="bot-special") is False
        assert self.store.is_enabled("ai", bot_id="bot-other") is True

    # ── Config CRUD ─────────────────────────────────────────────────────────

    def test_get_config_empty_default(self):
        assert self.store.get_config("ai") == {}

    def test_set_and_get_config(self):
        self.store.set_config("translation", {"work_lang": "zh", "target_lang": "en"})
        cfg = self.store.get_config("translation")
        assert cfg["work_lang"] == "zh"
        assert cfg["target_lang"] == "en"

    def test_set_config_merges(self):
        """set_config merges with existing, doesn't replace."""
        self.store.set_config("ai", {"model": "gpt-4"})
        self.store.set_config("ai", {"api_key": "sk-123"})
        cfg = self.store.get_config("ai")
        assert cfg["model"] == "gpt-4"
        assert cfg["api_key"] == "sk-123"

    def test_per_bot_config_override(self):
        """Bot-level config overrides global keys."""
        self.store.set_config("ai", {"model": "gpt-4", "api_key": "global-key"})
        self.store.set_config("ai", {"model": "gpt-5"}, bot_id="bot-1")
        # Global unchanged
        assert self.store.get_config("ai")["model"] == "gpt-4"
        # Bot override
        bot_cfg = self.store.get_config("ai", bot_id="bot-1")
        assert bot_cfg["model"] == "gpt-5"
        assert bot_cfg["api_key"] == "global-key"  # inherited from global

    # ── Export / Import ─────────────────────────────────────────────────────

    def test_export_all_roundtrip(self):
        """export_all → import_from should preserve state."""
        self.store.set_config("ai", {"model": "gpt-4"}, bot_id="bot-1")
        self.store.set_enabled("ai", False, bot_id="bot-1")
        self.store.set_config("translation", {"work_lang": "zh"})

        exported = self.store.export_all()
        assert len(exported) == 2

        # Import into a fresh store
        from agent.plugin.store import PluginStore
        store2 = PluginStore(":memory:")
        store2.start()
        store2.import_from(exported)

        assert store2.is_enabled("ai", bot_id="bot-1") is False
        assert store2.get_config("ai", bot_id="bot-1")["model"] == "gpt-4"
        assert store2.get_config("translation")["work_lang"] == "zh"

    # ── list_plugins ─────────────────────────────────────────────────────────

    def test_list_plugins_global(self):
        self.store.set_enabled("ai", True)
        self.store.set_enabled("translation", False)
        plugins = self.store.list_plugins()
        assert len(plugins) == 2
        names = {p["plugin_name"] for p in plugins}
        assert names == {"ai", "translation"}

    def test_list_plugins_per_bot(self):
        self.store.set_enabled("ai", False, bot_id="bot-1")
        plugins = self.store.list_plugins(bot_id="bot-1")
        assert len(plugins) == 1
        assert plugins[0]["plugin_name"] == "ai"


# ═══════════════════════════════════════════════════════════════════════════════
# PluginManager dispatch tests
# ═══════════════════════════════════════════════════════════════════════════════

class _TestReplyPlugin:
    """Fake plugin that always replies with a fixed text."""
    name = "test-reply"
    version = "0.1.0"
    priority = 50

    def __init__(self, reply_text="auto reply"):
        self.reply_text = reply_text

    async def on_message(self, ctx):
        from agent.plugin import ReplyAction
        return [ReplyAction(conversation_id=ctx.conversation_id, text=self.reply_text)]


class _TestEscalatePlugin:
    """Fake plugin that always escalates."""
    name = "test-escalate"
    version = "0.1.0"
    priority = 200

    async def on_message(self, ctx):
        from agent.plugin import EscalateAction
        return [EscalateAction(conversation_id=ctx.conversation_id, reason="test reason", priority="high")]


class _TestNoActionPlugin:
    """Fake plugin that takes no action."""
    name = "test-noop"
    version = "0.1.0"
    priority = 10

    async def on_message(self, ctx):
        from agent.plugin import NoAction
        return [NoAction()]


class TestPluginManager:
    """Unit tests for PluginManager dispatch."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from agent.plugin.manager import PluginManager
        # Use fresh plugin_store and manager
        from agent.plugin.store import PluginStore
        from agent.plugin import manager as pm_mod
        # Reset singleton state for test isolation
        store = PluginStore(":memory:")
        store.start()
        pm_mod.plugin_store = store

        self.mgr = PluginManager()
        self.store = store

    def test_register_and_get(self):
        plugin = _TestReplyPlugin()
        self.mgr.register(plugin)
        assert self.mgr.get("test-reply") is plugin
        assert "test-reply" in self.mgr.names

    def test_unregister(self):
        plugin = _TestReplyPlugin()
        self.mgr.register(plugin)
        self.mgr.unregister("test-reply")
        assert self.mgr.get("test-reply") is None
        assert "test-reply" not in self.mgr.names

    @pytest.mark.asyncio
    async def test_dispatch_reply_action(self):
        from agent.plugin import MessageContext
        self.mgr.register(_TestReplyPlugin("hello world"))
        ctx = MessageContext(
            bot_id="bot-1", jid="user@s.whatsapp.net",
            direction="incoming", content="ping",
            conversation_id="bot-1:user@s.whatsapp.net",
        )
        actions = await self.mgr.dispatch_on_message(ctx)
        assert len(actions) == 1
        from agent.plugin import ReplyAction
        assert isinstance(actions[0], ReplyAction)
        assert actions[0].text == "hello world"

    @pytest.mark.asyncio
    async def test_dispatch_escalate_action(self):
        from agent.plugin import MessageContext
        self.mgr.register(_TestEscalatePlugin())
        ctx = MessageContext(
            bot_id="bot-1", jid="user@s.whatsapp.net",
            direction="incoming", content="I want a refund!",
            conversation_id="bot-1:user@s.whatsapp.net",
        )
        actions = await self.mgr.dispatch_on_message(ctx)
        assert len(actions) == 1
        from agent.plugin import EscalateAction
        assert isinstance(actions[0], EscalateAction)
        assert actions[0].priority == "high"

    @pytest.mark.asyncio
    async def test_disabled_plugin_skipped(self):
        """Disabled plugin should not receive dispatch."""
        from agent.plugin import MessageContext
        self.mgr.register(_TestReplyPlugin("should not appear"))
        # Disable the plugin
        self.store.set_enabled("test-reply", False)
        ctx = MessageContext(
            bot_id="bot-1", jid="user@s.whatsapp.net",
            direction="incoming", content="ping",
            conversation_id="bot-1:user@s.whatsapp.net",
        )
        actions = await self.mgr.dispatch_on_message(ctx)
        assert len(actions) == 0

    @pytest.mark.asyncio
    async def test_dispatch_sorted_by_priority(self):
        """Plugins dispatch in ascending priority order."""
        from agent.plugin import MessageContext
        first = []
        second = []

        class Priority100(_TestReplyPlugin):
            name = "p100"
            priority = 100
            async def on_message(self, ctx):
                first.append(100)
                return await super().on_message(ctx)

        class Priority50(_TestReplyPlugin):
            name = "p50"
            priority = 50
            async def on_message(self, ctx):
                first.append(50)
                return await super().on_message(ctx)

        self.mgr.register(Priority100(""))
        self.mgr.register(Priority50(""))
        ctx = MessageContext(
            bot_id="bot-1", jid="user@s.whatsapp.net",
            direction="incoming", content="test",
            conversation_id="bot-1:user@s.whatsapp.net",
        )
        await self.mgr.dispatch_on_message(ctx)
        assert first == [50, 100], f"Expected [50, 100] (ascending priority), got {first}"

    @pytest.mark.asyncio
    async def test_dispatch_per_bot_disable(self):
        """Plugin disabled for specific bot should still run for others."""
        from agent.plugin import MessageContext
        self.mgr.register(_TestReplyPlugin("hi"))
        self.store.set_enabled("test-reply", False, bot_id="bot-disabled")

        ctx_good = MessageContext(
            bot_id="bot-good", jid="user@s.whatsapp.net",
            direction="incoming", content="ping",
            conversation_id="bot-good:user@s.whatsapp.net",
        )
        ctx_bad = MessageContext(
            bot_id="bot-disabled", jid="user@s.whatsapp.net",
            direction="incoming", content="ping",
            conversation_id="bot-disabled:user@s.whatsapp.net",
        )

        actions_good = await self.mgr.dispatch_on_message(ctx_good)
        actions_bad = await self.mgr.dispatch_on_message(ctx_bad)
        assert len(actions_good) == 1
        assert len(actions_bad) == 0
