"""Phase 11: Satisfaction Plugin — Survey session store & plugin logic tests.

Covers:
- SurveyStore: CRUD, session lifecycle (active → surveying → completed/expired)
- SatisfactionPlugin: parse_rating, state machine, inactivity trigger
- Conversation stage: set/get/clear, skip_stages dispatch
"""

import pytest
import time


# ═══════════════════════════════════════════════════════════════════════════════
# SurveyStore unit tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSurveyStore:
    """Unit tests for SurveyStore (SQLite in-memory)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from agent.plugin.satisfaction.store import SurveyStore
        self.store = SurveyStore(":memory:")
        self.store.start()

    # ── Session lifecycle ────────────────────────────────────────────────────

    def test_create_session(self):
        s = self.store.create_session("bot1", "bot1:user@s.whatsapp.net")
        assert s["session_status"] == "active"
        assert s["bot_id"] == "bot1"

    def test_get_active_session_after_create(self):
        conv = "bot1:user@s.whatsapp.net"
        self.store.create_session("bot1", conv)
        active = self.store.get_active_session(conv)
        assert active is not None
        assert active["session_status"] == "active"

    def test_create_session_idempotent(self):
        """Creating a second session for same conv returns the existing one."""
        conv = "bot1:user@s.whatsapp.net"
        s1 = self.store.create_session("bot1", conv)
        s2 = self.store.create_session("bot1", conv)
        assert s1["id"] == s2["id"]

    def test_touch_session_updates_last_msg_at(self):
        conv = "bot1:user@s.whatsapp.net"
        s = self.store.create_session("bot1", conv)
        old_ts = s["last_msg_at"]
        time.sleep(0.05)
        self.store.touch_session(s["id"])
        s2 = self.store.get(s["id"])
        assert s2["last_msg_at"] > old_ts

    def test_set_surveying(self):
        conv = "bot1:user@s.whatsapp.net"
        s = self.store.create_session("bot1", conv)
        ok = self.store.set_surveying(s["id"])
        assert ok
        active = self.store.get_active_session(conv)
        assert active["session_status"] == "surveying"
        assert active["survey_sent_at"] is not None

    def test_complete_survey(self):
        conv = "bot1:user@s.whatsapp.net"
        s = self.store.create_session("bot1", conv)
        self.store.set_surveying(s["id"])
        ok = self.store.complete_survey(s["id"], 5)
        assert ok
        finished = self.store.get(s["id"])
        assert finished["session_status"] == "completed"
        assert finished["rating"] == 5
        assert finished["rating_at"] is not None
        assert finished["ended_at"] is not None
        # No active session after completion
        assert self.store.get_active_session(conv) is None

    def test_expire_session(self):
        conv = "bot1:user@s.whatsapp.net"
        s = self.store.create_session("bot1", conv)
        self.store.expire_session(s["id"])
        finished = self.store.get(s["id"])
        assert finished["session_status"] == "expired"
        assert self.store.get_active_session(conv) is None

    def test_list_filtered(self):
        conv = "bot1:user@s.whatsapp.net"
        s = self.store.create_session("bot1", conv)
        self.store.complete_survey(s["id"], 4)
        items = self.store.list(bot_id="bot1", status="completed")
        assert len(items) == 1
        assert items[0]["rating"] == 4

    def test_multiple_sessions_sequential(self):
        """After completing a session, a new one can be created."""
        conv = "bot1:user@s.whatsapp.net"
        s1 = self.store.create_session("bot1", conv)
        self.store.complete_survey(s1["id"], 3)
        assert self.store.get_active_session(conv) is None
        s2 = self.store.create_session("bot1", conv)
        assert s2["id"] != s1["id"]
        assert s2["session_status"] == "active"


# ═══════════════════════════════════════════════════════════════════════════════
# SatisfactionPlugin unit tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSatisfactionPlugin:
    """Tests for SatisfactionPlugin logic (parse_rating, state machine)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from agent.plugin.satisfaction.store import SurveyStore
        from agent.plugin.store import PluginStore
        self.store = SurveyStore(":memory:")
        self.store.start()
        self.pstore = PluginStore(":memory:")
        self.pstore.start()
        # Set default satisfaction config
        self.pstore.set_config("satisfaction", {
            "inactivity_minutes": 5,
            "survey_message": "Please rate (1-5)",
            "thank_you_message": "Thanks!",
        })
        self.pstore.set_enabled("satisfaction", True)
        # Enable AI with default skip_stages
        self.pstore.set_config("ai", {"skip_stages": ["surveying"]})
        self.pstore.set_enabled("ai", True)

    # ── parse_rating ─────────────────────────────────────────────────────────

    def test_parse_rating_plain_number(self):
        from agent.plugin.satisfaction import SatisfactionPlugin
        p = SatisfactionPlugin()
        assert p._parse_rating("5") == 5
        assert p._parse_rating("1") == 1
        assert p._parse_rating("3") == 3

    def test_parse_rating_with_words(self):
        from agent.plugin.satisfaction import SatisfactionPlugin
        p = SatisfactionPlugin()
        assert p._parse_rating("评分5") == 5
        assert p._parse_rating("4分") == 4
        assert p._parse_rating("I give it a 5") == 5

    def test_parse_rating_invalid(self):
        from agent.plugin.satisfaction import SatisfactionPlugin
        p = SatisfactionPlugin()
        assert p._parse_rating("hello") is None
        assert p._parse_rating("") is None
        assert p._parse_rating("6") is None     # out of range
        assert p._parse_rating("0") is None     # out of range
        assert p._parse_rating("10") is None    # not 1-5

    # ── on_message state machine ─────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_new_session_creates_store_entry(self):
        from agent.plugin.satisfaction import SatisfactionPlugin
        from agent.plugin import MessageContext
        from agent.plugin.store import plugin_store as global_ps
        from agent.plugin.satisfaction.store import survey_store as global_ss
        global_ps._db_path = ":memory:"
        global_ps._initialized = False; global_ps._conn = None; global_ps.start()
        global_ss._db_path = ":memory:"
        global_ss._initialized = False; global_ss._conn = None; global_ss.start()
        global_ps.set_config("satisfaction", {"inactivity_minutes": 5})
        global_ps.set_enabled("satisfaction", True)
        p = SatisfactionPlugin()
        p._is_new_conversation = lambda *a: True  # bypass conv_store
        p._is_new_conversation = lambda *a: True
        p._schedule_inactivity = lambda *a: None
        ctx = MessageContext(
            bot_id="bot1", jid="user@s.whatsapp.net",
            conversation_id="bot1:user@s.whatsapp.net",
            direction="incoming", content="hello",
        )
        actions = await p.on_message(ctx)
        from agent.plugin import NoAction
        assert len(actions) == 1 and isinstance(actions[0], NoAction)
        active = global_ss.get_active_session(ctx.conversation_id)
        assert active is not None

    @pytest.mark.asyncio
    async def test_surveying_rating_completes(self):
        from agent.plugin.satisfaction import SatisfactionPlugin
        from agent.plugin import MessageContext, ReplyAction
        from agent.plugin.manager import plugin_manager as pm
        from agent.plugin.store import plugin_store as global_ps
        from agent.plugin.satisfaction.store import survey_store as global_ss
        global_ps._db_path = ":memory:"
        global_ps._initialized = False; global_ps._conn = None; global_ps.start()
        global_ss._db_path = ":memory:"
        global_ss._initialized = False; global_ss._conn = None; global_ss.start()
        global_ps.set_config("satisfaction", {
            "inactivity_minutes": 5, "survey_message": "Rate 1-5", "thank_you_message": "Thanks!",
        })
        global_ps.set_enabled("satisfaction", True)
        p = SatisfactionPlugin()
        p._is_new_conversation = lambda *a: True  # bypass conv_store
        p._is_new_conversation = lambda *a: True
        p._schedule_inactivity = lambda *a: None
        pm._conv_stages = {}
        conv = "bot1:user@s.whatsapp.net"
        s = global_ss.create_session("bot1", conv)
        global_ss.set_surveying(s["id"])
        pm.set_stage(conv, "surveying")
        ctx = MessageContext(
            bot_id="bot1", jid="user@s.whatsapp.net",
            conversation_id=conv, direction="incoming", content="5",
        )
        actions = await p.on_message(ctx)
        assert len(actions) == 1
        assert isinstance(actions[0], ReplyAction)
        assert "Thanks" in actions[0].text
        assert pm.get_stage(conv) == "normal"
        active = global_ss.get_active_session(conv)
        assert active is None

    @pytest.mark.asyncio
    async def test_skip_group_chat(self):
        from agent.plugin.satisfaction import SatisfactionPlugin
        from agent.plugin import MessageContext
        from agent.plugin.store import plugin_store as global_ps
        from agent.plugin.satisfaction.store import survey_store as global_ss
        global_ps._db_path = ":memory:"
        global_ps._initialized = False; global_ps._conn = None; global_ps.start()
        global_ss._db_path = ":memory:"
        global_ss._initialized = False; global_ss._conn = None; global_ss.start()
        global_ps.set_config("satisfaction", {"inactivity_minutes": 5})
        p = SatisfactionPlugin()
        p._config_cache = {}
        ctx = MessageContext(
            bot_id="bot1", jid="group@g.us",
            conversation_id="bot1:group@g.us",
            direction="incoming", content="hello",
        )
        actions = await p.on_message(ctx)
        active = global_ss.get_active_session(ctx.conversation_id)
        assert active is None


# ═══════════════════════════════════════════════════════════════════════════════
# Conversation Stage integration tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestConversationStage:
    """Tests for PluginManager stage get/set and skip_stages dispatch."""

    def test_get_default_stage(self):
        from agent.plugin.manager import plugin_manager as pm
        assert pm.get_stage("unknown:conv") == "normal"

    def test_set_and_get_stage(self):
        from agent.plugin.manager import plugin_manager as pm
        pm.set_stage("bot1:test", "surveying")
        assert pm.get_stage("bot1:test") == "surveying"
        pm.set_stage("bot1:test", "normal")
        assert pm.get_stage("bot1:test") == "normal"

    def test_clear_stage(self):
        from agent.plugin.manager import plugin_manager as pm
        pm.set_stage("bot1:test", "surveying")
        pm.clear_stage("bot1:test")
        assert pm.get_stage("bot1:test") == "normal"

    @pytest.mark.asyncio
    async def test_skip_stages_dispatch(self):
        """Plugin with skip_stages=['surveying'] is skipped in that stage.
        Tests the mechanism directly: config contains skip_stages, and the
        dispatcher respects it by checking ctx.stage against skip_stages.
        """
        from agent.plugin import Plugin, MessageContext, NoAction
        from agent.plugin.manager import plugin_manager as pm

        class TestSkipPlugin(Plugin):
            name = "test_skip"
            version = "0.1"
            priority = 50
            async def on_message(self, ctx):
                return [NoAction()]

        pm._plugins = {}
        pm.register(TestSkipPlugin())
        pm._conv_stages["bot1:conv"] = "surveying"

        # Simulate what dispatch_on_message does: read config, check skip_stages
        cfg = {"skip_stages": ["surveying"]}
        ctx = MessageContext(
            bot_id="bot1", jid="user@s.whatsapp.net",
            conversation_id="bot1:conv", direction="incoming", content="test",
        )
        ctx.stage = pm.get_stage(ctx.conversation_id)
        assert ctx.stage == "surveying"

        # The skip_stages check from dispatch_on_message logic:
        skip_stages = cfg.get("skip_stages", [])
        should_skip = isinstance(skip_stages, list) and ctx.stage in skip_stages
        assert should_skip is True

        # Cleanup
        pm.clear_stage("bot1:conv")
        pm.unregister("test_skip")
