"""
Phase 5 tests �?CallManager + CallSession lifecycle.

Tests: outgoing call flow, incoming call flow, accept/reject/end,
audio pipeline wiring, state machine integration, cleanup.

Uses mock zowsup client (no real WhatsApp connection needed).
"""

import sys, os
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import asyncio
import pytest
from voip.call.call_state import CallState, CallDirection, EndReason, Transition, CallInfo
from voip.call.call_manager import CallManager, CallError
from voip.call.call_session import CallSession


# ── Mock zowsup client ────────────────────────────────────────

class MockZowsupClient:
    """Simulates zowsup protocol layer for testing CallManager."""

    def __init__(self):
        self.botId = "test_bot"
        self.idType = None
        self.own_jid = "self:0@s.whatsapp.net"
        self.sent_nodes: list = []
        self.query_responses: dict = {}
        self.ack_nodes: list = []
        self.iq_responses: dict = {}

        # botLayer mock
        self.botLayer = _MockBotLayer(self)

        # profile.config mock
        class _ProfileConfig:
            lid = self.own_jid
        class _Profile:
            config = _ProfileConfig()
        self.profile = _Profile()

    async def send_query(self, node):
        self.sent_nodes.append(node)
        return self.query_responses.get("default")

    async def send_node(self, node):
        self.sent_nodes.append(node)

    async def send_iq(self, entity):
        return self.iq_responses.get("default", {})


class _MockBotLayer:
    def __init__(self, client: MockZowsupClient):
        self._client = client
        self.db = None
    async def _send_call_query(self, entity):
        return await self._client.send_query(entity)
    async def _send_call_node(self, entity):
        return await self._client.send_node(entity)
    async def _sendIqAsync(self, entity):
        return await self._client.send_iq(entity)
    def getProp(self, name, default=None):
        return default


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def cm():
    mgr = CallManager()
    yield mgr
    # Cleanup
    try:
        asyncio.get_event_loop().run_until_complete(mgr.close())
    except Exception:
        pass


@pytest.fixture
def mock_client():
    return MockZowsupClient()


# ── Helpers ───────────────────────────────────────────────────

def _wire(cm, mock):
    cm.set_context(mock)


def _get_session(cm) -> CallSession:
    """Get the most recent active session from CallManager."""
    for s in cm._sessions.values():
        if s.is_active():
            return s
    if cm._sessions:
        return list(cm._sessions.values())[-1]
    return None


# ── Tests ─────────────────────────────────────────────────────

class TestCallManagerInit:
    def test_initial_state(self, cm):
        assert cm.current_call is None
        assert len(cm._sessions) == 0

    def test_set_context(self, cm, mock_client):
        cm.set_context(mock_client)
        assert cm._bot is not None
        assert cm._bot.botId == "test_bot"

    def test_codec_initialized_on_call(self, cm):
        # CallSession has codec init �?verify via session
        session = CallSession("TEST001")
        session._init_codec()
        assert session._codec is not None
        assert session._codec.frame_size() == 960


class TestOutgoingCallFlow:
    def test_start_call_state_transition(self, cm, mock_client):
        """start_call transitions to RINGING after offer sent."""
        _wire(cm, mock_client)

        # Override _build_offer_node on the session that will be created
        # We need to intercept session creation
        original_create = cm._create_session
        def patched_create(call_id):
            session = original_create(call_id)
            async def _mock_build(cid, ck, peer):
                return object()
            session._build_offer_node = _mock_build
            return session
        cm._create_session = patched_create

        async def _run():
            await cm.start_call("peer@s.whatsapp.net")

        asyncio.run(_run())
        assert cm.current_call is not None
        assert cm.current_call.state == CallState.RINGING
        assert cm.current_call.direction == CallDirection.OUTGOING

    def test_start_call_generates_keys(self, cm, mock_client):
        _wire(cm, mock_client)
        original_create = cm._create_session
        def patched_create(call_id):
            session = original_create(call_id)
            async def _mock_build(cid, ck, peer):
                return object()
            session._build_offer_node = _mock_build
            return session
        cm._create_session = patched_create

        async def _run():
            await cm.start_call("peer@s.whatsapp.net")

        asyncio.run(_run())
        call = cm.current_call
        assert call.encryption_key is not None
        assert len(call.encryption_key) == 32
        session = _get_session(cm)
        assert session._self_ssrc != 0
        assert len(session._peer_ssrcs) == 1

    def test_state_change_callback_fires(self, cm, mock_client):
        _wire(cm, mock_client)
        original_create = cm._create_session
        def patched_create(call_id):
            session = original_create(call_id)
            async def _mock_build(cid, ck, peer):
                return object()
            session._build_offer_node = _mock_build
            return session
        cm._create_session = patched_create

        states = []
        cm.on_state_change = lambda session, info: states.append(info.state)

        async def _run():
            await cm.start_call("peer@s.whatsapp.net")

        asyncio.run(_run())
        assert len(states) >= 1
        assert CallState.RINGING in states


class TestIncomingCallFlow:
    def test_relaylatency_sent_when_relay_connects_before_active_state(self):
        session = CallSession("TEST_RELAY_001", None, None, "self:0@s.whatsapp.net")
        call = CallInfo.new_outgoing("TEST_RELAY_001", "peer@s.whatsapp.net", "self:0@s.whatsapp.net")
        call.apply_transition(Transition.OFFER_SENT)
        session._call = call

        async def fake_send_node(node):
            session.sent_node = node

        session._send_node = fake_send_node
        session._relay.get_relay_entries = lambda: [{
            "relay_name": "relay-1",
            "rtt_ms": 12,
            "addr_bytes": b"\x01\x02\x03\x04\x05\x06",
        }]

        async def _run():
            session._on_relay_connected()
            await asyncio.sleep(0)

        asyncio.run(_run())

        assert hasattr(session, "sent_node")
        assert getattr(session, "sent_node") is not None

    def test_handle_offer_creates_call(self, cm, mock_client):
        """handle_call_offer creates incoming call in INCOMING_RINGING state."""
        _wire(cm, mock_client)

        class MockOffer:
            def getType(self): return "offer"
            def getCallId(self): return "INC_CALL_001"
            def getFrom(self): return "peer@s.whatsapp.net"
            def getCallCreator(self): return "peer@s.whatsapp.net"
            callKey = b"\xAB" * 32
            def toProtocolTreeNode(self): return None

        cm.on_call_entity(MockOffer())
        assert cm.current_call is not None
        assert cm.current_call.state == CallState.INCOMING_RINGING
        assert cm.current_call.direction == CallDirection.INCOMING
        assert cm.current_call.encryption_key == b"\xAB" * 32

    def test_incoming_callback_fires(self, cm, mock_client):
        _wire(cm, mock_client)
        incoming_calls = []
        cm.on_incoming = lambda session, info: incoming_calls.append(info)

        class MockOffer:
            def getType(self): return "offer"
            def getCallId(self): return "INC_002"
            def getFrom(self): return "peer@s.whatsapp.net"
            def getCallCreator(self): return "peer@s.whatsapp.net"
            callKey = b"\xCD" * 32
            def toProtocolTreeNode(self): return None

        cm.on_call_entity(MockOffer())
        assert len(incoming_calls) == 1
        assert incoming_calls[0].call_id == "INC_002"

    def test_accept_incoming_call(self, cm, mock_client):
        _wire(cm, mock_client)

        class MockOffer:
            def getType(self): return "offer"
            def getCallId(self): return "INC_003"
            def getFrom(self): return "peer@s.whatsapp.net"
            def getCallCreator(self): return "peer@s.whatsapp.net"
            callKey = b"\xEF" * 32
            def toProtocolTreeNode(self): return None

        cm.on_call_entity(MockOffer())

        async def _run():
            await cm.accept_call("INC_003")

        asyncio.run(_run())
        assert cm.current_call.state == CallState.CONNECTING

    def test_accept_rejects_wrong_state(self, cm, mock_client):
        _wire(cm, mock_client)
        original_create = cm._create_session
        def patched_create(call_id):
            session = original_create(call_id)
            async def _mock_build(cid, ck, peer):
                return object()
            session._build_offer_node = _mock_build
            return session
        cm._create_session = patched_create

        async def _run():
            await cm.start_call("peer@s.whatsapp.net")
            with pytest.raises(CallError, match="No incoming call"):
                await cm.accept_call()

        asyncio.run(_run())


class TestEndCall:
    def test_end_call_transitions_to_ended(self, cm, mock_client):
        _wire(cm, mock_client)
        original_create = cm._create_session
        def patched_create(call_id):
            session = original_create(call_id)
            async def _mock_build(cid, ck, peer):
                return object()
            session._build_offer_node = _mock_build
            return session
        cm._create_session = patched_create

        async def _run():
            await cm.start_call("peer@s.whatsapp.net")
            call_id = cm.current_call.call_id
            await cm.end_call(call_id)

        asyncio.run(_run())
        # After end, session is removed from registry
        # current_call may return the ended call or None
        assert cm.current_call is None or cm.current_call.state == CallState.ENDED

    def test_end_callback_fires(self, cm, mock_client):
        _wire(cm, mock_client)
        original_create = cm._create_session
        def patched_create(call_id):
            session = original_create(call_id)
            async def _mock_build(cid, ck, peer):
                return object()
            session._build_offer_node = _mock_build
            return session
        cm._create_session = patched_create

        ended = []
        cm.on_ended = lambda session, info: ended.append(info)

        async def _run():
            await cm.start_call("peer@s.whatsapp.net")
            call_id = cm.current_call.call_id
            await cm.end_call(call_id)

        asyncio.run(_run())
        assert len(ended) == 1

    def test_end_call_idempotent(self, cm, mock_client):
        _wire(cm, mock_client)
        original_create = cm._create_session
        def patched_create(call_id):
            session = original_create(call_id)
            async def _mock_build(cid, ck, peer):
                return object()
            session._build_offer_node = _mock_build
            return session
        cm._create_session = patched_create

        async def _run():
            await cm.start_call("peer@s.whatsapp.net")
            call_id = cm.current_call.call_id
            await cm.end_call(call_id)
            await cm.end_call(call_id)  # Should not raise

        asyncio.run(_run())


class TestRejectCall:
    def test_reject_incoming(self, cm, mock_client):
        _wire(cm, mock_client)

        class MockOffer:
            def getType(self): return "offer"
            def getCallId(self): return "INC_REJ"
            def getFrom(self): return "peer@s.whatsapp.net"
            def getCallCreator(self): return "peer@s.whatsapp.net"
            callKey = b"\x11" * 32
            def toProtocolTreeNode(self): return None

        cm.on_call_entity(MockOffer())

        async def _run():
            await cm.reject_call("INC_REJ", EndReason.BUSY)

        asyncio.run(_run())
        # After reject, session is cleaned up
        assert cm.get_call("INC_REJ") is None or cm.get_call("INC_REJ").state == CallState.ENDED


class TestAudioPipeline:
    def test_feed_audio_no_tx_is_safe(self, cm):
        """feed_audio before pipeline init should not crash."""
        cm.feed_audio("nonexistent", [0.1] * 100)

    def test_srtp_keys_derived_on_init(self, cm, mock_client):
        _wire(cm, mock_client)
        original_create = cm._create_session
        def patched_create(call_id):
            session = original_create(call_id)
            async def _mock_build(cid, ck, peer):
                return object()
            session._build_offer_node = _mock_build
            return session
        cm._create_session = patched_create

        async def _run():
            await cm.start_call("peer@s.whatsapp.net")
            session = _get_session(cm)
            session._init_srtp_keys()

        asyncio.run(_run())
        session = _get_session(cm)
        if session and session._call and not session._call.is_ended():
            assert session._srtp_send is not None
            assert session._srtp_recv is not None


class TestHandleTerminate:
    def test_remote_terminate_ends_call(self, cm, mock_client):
        _wire(cm, mock_client)
        original_create = cm._create_session
        def patched_create(call_id):
            session = original_create(call_id)
            async def _mock_build(cid, ck, peer):
                return object()
            session._build_offer_node = _mock_build
            return session
        cm._create_session = patched_create

        async def _run():
            await cm.start_call("peer@s.whatsapp.net")

        asyncio.run(_run())
        call_id = cm.current_call.call_id

        class MockTerminate:
            def getType(self): return "terminate"
            def getCallId(self): return call_id

        cm.on_call_entity(MockTerminate())
        # Session should be removed after terminate
        assert cm.get_call(call_id) is None or cm.get_call(call_id).state == CallState.ENDED

    def test_terminate_fires_ended_callback(self, cm, mock_client):
        _wire(cm, mock_client)
        original_create = cm._create_session
        def patched_create(call_id):
            session = original_create(call_id)
            async def _mock_build(cid, ck, peer):
                return object()
            session._build_offer_node = _mock_build
            return session
        cm._create_session = patched_create

        ended = []
        cm.on_ended = lambda session, info: ended.append(info)

        async def _run():
            await cm.start_call("peer@s.whatsapp.net")

        asyncio.run(_run())
        call_id = cm.current_call.call_id

        class MockTerminate:
            def getType(self): return "terminate"
            def getCallId(self): return call_id

        cm.on_call_entity(MockTerminate())
        assert len(ended) == 1


class TestMultiSession:
    """Tests for multi-call support �?the key feature of CallSession separation."""

    def test_two_concurrent_calls(self, cm, mock_client):
        """Two calls with different call_ids can coexist."""
        _wire(cm, mock_client)

        class MockOffer1:
            def getType(self): return "offer"
            def getCallId(self): return "CALL_A"
            def getFrom(self): return "peer1@s.whatsapp.net"
            def getCallCreator(self): return "peer1@s.whatsapp.net"
            callKey = b"\xAA" * 32
            def toProtocolTreeNode(self): return None

        class MockOffer2:
            def getType(self): return "offer"
            def getCallId(self): return "CALL_B"
            def getFrom(self): return "peer2@s.whatsapp.net"
            def getCallCreator(self): return "peer2@s.whatsapp.net"
            callKey = b"\xBB" * 32
            def toProtocolTreeNode(self): return None

        cm.on_call_entity(MockOffer1())
        cm.on_call_entity(MockOffer2())

        assert cm.get_call("CALL_A") is not None
        assert cm.get_call("CALL_B") is not None
        assert cm.get_call("CALL_A").peer_jid == "peer1@s.whatsapp.net"
        assert cm.get_call("CALL_B").peer_jid == "peer2@s.whatsapp.net"
        assert len(cm.active_call_ids) == 2

    def test_terminate_one_does_not_affect_other(self, cm, mock_client):
        """Terminating one call doesn't affect the other."""
        _wire(cm, mock_client)

        class MockOffer1:
            def getType(self): return "offer"
            def getCallId(self): return "CALL_X"
            def getFrom(self): return "peer1@s.whatsapp.net"
            def getCallCreator(self): return "peer1@s.whatsapp.net"
            callKey = b"\xAA" * 32
            def toProtocolTreeNode(self): return None

        class MockOffer2:
            def getType(self): return "offer"
            def getCallId(self): return "CALL_Y"
            def getFrom(self): return "peer2@s.whatsapp.net"
            def getCallCreator(self): return "peer2@s.whatsapp.net"
            callKey = b"\xBB" * 32
            def toProtocolTreeNode(self): return None

        cm.on_call_entity(MockOffer1())
        cm.on_call_entity(MockOffer2())

        # Terminate CALL_X
        class MockTerminate:
            def getType(self): return "terminate"
            def getCallId(self): return "CALL_X"

        cm.on_call_entity(MockTerminate())

        # CALL_Y should still be active
        assert cm.get_call("CALL_Y") is not None
        assert cm.get_call("CALL_Y").state == CallState.INCOMING_RINGING
        assert "CALL_Y" in cm.active_call_ids

