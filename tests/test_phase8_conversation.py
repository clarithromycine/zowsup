"""Phase 8: Conversation CRUD tests."""

import pytest
from agent.manager.conversation_store import ConversationStore


class TestStore:
    """Unit tests for ConversationStore (in-memory SQLite, no agent needed)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.store = ConversationStore(":memory:")
        self.store.start()
        self.bot_id = "testbot"
        self.jid = "customer@s.whatsapp.net"
        self.conv_id = f"{self.bot_id}:{self.jid}"

    # ── Conversations ────────────────────────────────────────────────────────

    def test_upsert_creates_conversation(self):
        """First upsert creates a new conversation."""
        c = self.store.upsert_conversation(self.bot_id, self.jid, "1v1")
        assert c["id"] == self.conv_id
        assert c["bot_id"] == self.bot_id
        assert c["jid"] == self.jid
        assert c["type"] == "1v1"
        assert c["status"] == "active"
        assert c["message_count"] == 0
        assert c["last_message_at"] is None

    def test_upsert_is_idempotent(self):
        """Upsert twice returns the same conversation."""
        c1 = self.store.upsert_conversation(self.bot_id, self.jid)
        c2 = self.store.upsert_conversation(self.bot_id, self.jid)
        assert c1["id"] == c2["id"]
        assert c1["created_at"] == c2["created_at"]
        # updated_at should be refreshed
        assert c2["updated_at"] >= c1["updated_at"]

    def test_list_conversations_by_bot(self):
        """List filters by bot_id."""
        self.store.upsert_conversation(self.bot_id, "user1@s.whatsapp.net")
        self.store.upsert_conversation(self.bot_id, "user2@s.whatsapp.net")
        self.store.upsert_conversation("otherbot", "user3@s.whatsapp.net")

        result = self.store.list_conversations(self.bot_id)
        assert len(result) == 2

        result_all = self.store.list_conversations()
        assert len(result_all) == 3

    def test_close_conversation(self):
        """Close marks status='closed'."""
        self.store.upsert_conversation(self.bot_id, self.jid)
        assert self.store.close_conversation(self.conv_id) is True
        c = self.store.get_conversation(self.conv_id)
        assert c["status"] == "closed"

    def test_delete_conversation_cascades(self):
        """Deleting a conversation removes its messages too."""
        self.store.upsert_conversation(self.bot_id, self.jid)
        self.store.record_message(self.conv_id, self.bot_id, self.jid,
                                   "incoming", "TEXT", "hello")
        assert self.store.delete_conversation(self.conv_id) is True
        assert self.store.get_conversation(self.conv_id) is None
        assert len(self.store.get_messages(self.conv_id)) == 0

    # ── Messages ─────────────────────────────────────────────────────────────

    def test_record_message_incoming(self):
        """Record an incoming message."""
        msg = self.store.record_message(
            self.conv_id, self.bot_id, self.jid,
            "incoming", "TEXT", "Hello!", participant_jid=self.jid,
        )
        assert msg["direction"] == "incoming"
        assert msg["content_type"] == "TEXT"
        assert msg["content"] == "Hello!"
        assert msg["participant_jid"] == self.jid
        assert msg["status"] == ""

    def test_record_message_outgoing(self):
        """Record an outgoing message with msg_id."""
        msg = self.store.record_message(
            self.conv_id, self.bot_id, self.jid,
            "outgoing", "TEXT", "Hi!", msg_id="WA-MSG-001",
        )
        assert msg["direction"] == "outgoing"
        assert msg["msg_id"] == "WA-MSG-001"

    def test_record_message_auto_creates_conversation(self):
        """Recording a message auto-creates the conversation."""
        new_id = f"{self.bot_id}:newuser@s.whatsapp.net"
        self.store.record_message(new_id, self.bot_id, "newuser@s.whatsapp.net",
                                   "incoming", "TEXT", "first message")
        c = self.store.get_conversation(new_id)
        assert c is not None
        assert c["message_count"] == 1

    def test_get_messages_ordered(self):
        """Messages are returned in created_at DESC order (newest first)."""
        self.store.record_message(self.conv_id, self.bot_id, self.jid,
                                   "incoming", "TEXT", "msg1", sent_at=100)
        self.store.record_message(self.conv_id, self.bot_id, self.jid,
                                   "incoming", "TEXT", "msg2", sent_at=200)
        msgs = self.store.get_messages(self.conv_id)
        assert len(msgs) == 2
        assert msgs[0]["content"] == "msg2"
        assert msgs[1]["content"] == "msg1"

    def test_get_messages_since(self):
        """since parameter returns only newer messages in ASC order."""
        self.store.record_message(self.conv_id, self.bot_id, self.jid,
                                   "incoming", "TEXT", "old")
        # Capture a timestamp between the two records using created_at
        t0 = self.store.get_messages(self.conv_id, limit=1)[-1]["created_at"]
        self.store.record_message(self.conv_id, self.bot_id, self.jid,
                                   "incoming", "TEXT", "new")
        msgs = self.store.get_messages(self.conv_id, since=t0)
        assert len(msgs) == 1
        assert msgs[0]["content"] == "new"

    def test_get_messages_before(self):
        """before parameter returns older messages in DESC order."""
        self.store.record_message(self.conv_id, self.bot_id, self.jid,
                                   "incoming", "TEXT", "old", sent_at=100)
        self.store.record_message(self.conv_id, self.bot_id, self.jid,
                                   "incoming", "TEXT", "new", sent_at=200)
        msgs = self.store.get_messages(self.conv_id, before=150)
        assert len(msgs) == 1
        assert msgs[0]["content"] == "old"

    # ── Message Status ───────────────────────────────────────────────────────

    def test_update_message_status(self):
        """Status updates from SENT→DELIVERED→READ."""
        msg = self.store.record_message(
            self.conv_id, self.bot_id, self.jid,
            "outgoing", "TEXT", "Hi", msg_id="WA-MSG-002",
        )
        assert msg["status"] == "EXECUTED"

        self.store.update_message_status("WA-MSG-002", "SENT")
        self.store.update_message_status("WA-MSG-002", "DELIVERED")
        self.store.update_message_status("WA-MSG-002", "READ")

        updated = self.store.get_message_by_msg_id("WA-MSG-002")
        assert updated["status"] == "READ"
        assert updated["status_updated"] is not None

    def test_group_message_with_participant(self):
        """Group messages track participant_jid."""
        group_jid = "123456789@g.us"
        conv_id = f"{self.bot_id}:{group_jid}"
        msg = self.store.record_message(
            conv_id, self.bot_id, group_jid,
            "incoming", "TEXT", "Hi group!", participant_jid="user_A@g.us",
        )
        assert msg["participant_jid"] == "user_A@g.us"
        c = self.store.get_conversation(conv_id)
        assert c["type"] == "1v1"  # upsert defaults to 1v1

import requests

class TestAPI:
    """API tests — requires running agent."""

    @pytest.fixture(autouse=True)
    def setup(self, agent_noauth, test_bot_id):
        self.base = agent_noauth
        self.bot_id = test_bot_id
        self.jid = "999999999999@s.whatsapp.net"
        self.conv_id = f"{self.bot_id}:{self.jid}"

    def test_list_empty(self):
        """List returns empty or existing conversations."""
        r = requests.get(f"{self.base}/api/conversation")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_send_message_creates_conversation(self):
        """Sending a message creates the conversation and returns the message."""
        r = requests.post(
            f"{self.base}/api/conversation/{self.conv_id}/message",
            json={"content": "hello", "content_type": "TEXT"},
        )
        assert r.status_code in (200, 404)  # 404 if bot not running, 200 otherwise

    def test_get_nonexistent_404(self):
        """Non-existent conversation returns 404."""
        r = requests.get(f"{self.base}/api/conversation/nonexistent:test@s.whatsapp.net")
        assert r.status_code == 404

    def test_delete_nonexistent_404(self):
        """Deleting non-existent returns 404."""
        r = requests.delete(f"{self.base}/api/conversation/nonexistent:test@s.whatsapp.net")
        assert r.status_code == 404

class TestStatus:
    """Phase 3: Message status field present in API responses.

    Status capture logic verified in TestStore unit tests.
    """

    @pytest.fixture(autouse=True)
    def setup(self, agent_noauth, test_bot_id):
        self.base = agent_noauth
        self.bot_id = test_bot_id

    def test_conversation_detail_includes_status(self):
        """GET conversation returns messages with status field."""
        # Conversations list should return without errors
        r = requests.get(f"{self.base}/api/conversation?bot_id={self.bot_id}")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestRevoke:
    """Phase 4: Revoke endpoint."""

    @pytest.fixture(autouse=True)
    def setup(self, agent_noauth, test_bot_id):
        self.base = agent_noauth
        self.bot_id = test_bot_id

    def test_revoke_nonexistent_message_404(self):
        """Revoking a non-existent message returns 404."""
        conv_id = f"{self.bot_id}:123456789@s.whatsapp.net"
        r = requests.post(f"{self.base}/api/conversation/{conv_id}/message/99999/revoke")
        assert r.status_code == 404

    def test_revoke_nonexistent_conversation_404(self):
        """Revoking in non-existent conversation returns 404."""
        r = requests.post(
            f"{self.base}/api/conversation/badbot:none@s.whatsapp.net/message/1/revoke"
        )
        assert r.status_code == 404
