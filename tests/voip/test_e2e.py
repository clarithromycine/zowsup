"""
Phase 7 — End-to-end integration tests (mock).

Verifies the full integration chain:
  VoipAdapter → CallManager → Signaling → Media → Transport → Bridge

Uses mock zowsup client (no real WhatsApp connection needed).
"""

import sys, os
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import asyncio
import math
import pytest

from voip.voip_adapter import VoipAdapter
from voip.call.call_state import CallState, CallDirection, EndReason
from voip.bridge import BrowserBridge
from voip.media.pcm import float32_to_int16le


# ── Constants ──────────────────────────────────────────────────

TEST_BOT_ID = "test_bot_001"
TEST_PEER_JID = "peer@s.whatsapp.net"
TEST_OWN_JID = "test_bot_001@s.whatsapp.net"


def _patch_offer(mgr):
    """Patch _build_offer_node on CallManager to intercept session creation."""
    original = mgr._create_session
    def patched_create(call_id):
        session = original(call_id)
        async def _mock_build(cid, ck, peer):
            return object()
        session._build_offer_node = _mock_build
        return session
    mgr._create_session = patched_create


# ── Mock zowsup socket ────────────────────────────────────────


class MockZowsupSocket:
    """Simulates a bot for VoipAdapter integration tests."""

    def __init__(self, own_jid="peer@s.whatsapp.net"):
        self.botId = "test_bot"
        self.idType = None
        self.own_jid = own_jid
        self.sent_nodes: list = []
        self.ack_responses: dict = {}
        self.iq_responses: dict = {}
        self._next_call_id = None

        # botLayer mock
        class _MockLayer:
            def __init__(self, client):
                self._client = client
                self.db = None
            async def _send_call_query(self, entity):
                return self._client.ack_responses.get("default")
            async def _send_call_node(self, entity):
                self._client.sent_nodes.append(("send", entity))
            async def _sendIqAsync(self, entity):
                return self._client.iq_responses.get("default", {})
            def getProp(self, name, default=None):
                return default
        self.botLayer = _MockLayer(self)

        # profile.config mock
        class _ProfileConfig:
            def __init__(self, jid):
                self.lid = jid
        class _Profile:
            def __init__(self, jid):
                self.config = _ProfileConfig(jid)
        self.profile = _Profile(own_jid)

    async def send_query(self, node):
        self.sent_nodes.append(("query", node))
        return self.ack_responses.get("default")

    async def send_node(self, node):
        self.sent_nodes.append(("send", node))

    async def send_iq(self, entity):
        return self.iq_responses.get("default", {})


# ── Tests ─────────────────────────────────────────────────────


class TestVoipAdapterIntegration:
    """Integration tests for VoipAdapter with mock zowsup."""

    @pytest.fixture
    def adapter(self):
        adapter = VoipAdapter()
        adapter.start()

        # Register mock bot
        mock = MockZowsupSocket(TEST_OWN_JID)
        adapter.register_bot(TEST_BOT_ID, mock)

        yield adapter
        adapter.stop()

    @pytest.mark.asyncio
    async def test_start_call_creates_callmanager(self, adapter):
        """start_call creates a CallManager and returns call_id."""
        # Override build_offer to avoid real zowsup call
        mgr = adapter._get_manager(TEST_BOT_ID)
        _patch_offer(mgr)

        result = await adapter.start_call(TEST_BOT_ID, TEST_PEER_JID)
        assert "call_id" in result
        assert result["state"] == CallState.RINGING.value

    @pytest.mark.asyncio
    async def test_incoming_call_flow(self, adapter):
        """Simulate incoming call → accept → state transitions."""
        mgr = adapter._get_manager(TEST_BOT_ID)
        _patch_offer(mgr)

        # Simulate incoming offer via protocol hook
        class MockOffer:
            def getCallId(self): return "INC_E2E_001"
            def getFrom(self): return TEST_PEER_JID
            def getCallCreator(self): return TEST_PEER_JID
            def getType(self): return "offer"
            callKey = b"\xAB" * 32

        adapter.on_call_entity(TEST_BOT_ID, MockOffer())
        call = mgr.current_call
        assert call is not None
        assert call.state == CallState.INCOMING_RINGING
        assert call.direction == CallDirection.INCOMING

        # Accept
        result = await adapter.accept_call(TEST_BOT_ID)
        assert result["state"] == CallState.CONNECTING.value

    @pytest.mark.asyncio
    async def test_end_call_flow(self, adapter):
        """Start → end call via adapter API."""
        mgr = adapter._get_manager(TEST_BOT_ID)
        _patch_offer(mgr)

        await adapter.start_call(TEST_BOT_ID, TEST_PEER_JID)
        result = await adapter.end_call(TEST_BOT_ID)
        assert result["state"] == "ended"

    @pytest.mark.asyncio
    async def test_event_bus(self, adapter):
        """Event bus emits state changes and incoming events."""
        events = []
        adapter.add_listener(lambda etype, data: events.append((etype, data)))

        mgr = adapter._get_manager(TEST_BOT_ID)
        _patch_offer(mgr)

        await adapter.start_call(TEST_BOT_ID, TEST_PEER_JID)

        # Should have at least one state_change event
        state_events = [e for e in events if e[0] == "state_change"]
        assert len(state_events) >= 1
        assert state_events[0][1]["state"] == CallState.RINGING.value

    @pytest.mark.asyncio
    async def test_incoming_event(self, adapter):
        """Incoming call fires 'incoming' event."""
        events = []
        adapter.add_listener(lambda etype, data: events.append((etype, data)))

        class MockOffer:
            def getCallId(self): return "INC_EVT_001"
            def getFrom(self): return TEST_PEER_JID
            def getCallCreator(self): return TEST_PEER_JID
            def getType(self): return "offer"
            callKey = b"\xCD" * 32

        adapter.on_call_entity(TEST_BOT_ID, MockOffer())

        incoming_events = [e for e in events if e[0] == "incoming"]
        assert len(incoming_events) == 1
        assert incoming_events[0][1]["call_id"] == "INC_EVT_001"

    @pytest.mark.asyncio
    async def test_ended_event(self, adapter):
        """End call fires 'ended' event."""
        events = []
        adapter.add_listener(lambda etype, data: events.append((etype, data)))

        mgr = adapter._get_manager(TEST_BOT_ID)
        _patch_offer(mgr)
        await adapter.start_call(TEST_BOT_ID, TEST_PEER_JID)
        await adapter.end_call(TEST_BOT_ID)

        ended_events = [e for e in events if e[0] == "ended"]
        assert len(ended_events) == 1

    @pytest.mark.asyncio
    async def test_bridge_attach(self, adapter):
        """attach_bridge creates BrowserBridge and returns SDP answer."""
        from aiortc import RTCPeerConnection
        import asyncio as _asyncio

        mgr = adapter._get_manager(TEST_BOT_ID)
        _patch_offer(mgr)
        await adapter.start_call(TEST_BOT_ID, TEST_PEER_JID)
        mgr.current_call.apply_transition("media_connected")

        # Create a browser-side PeerConnection to get a real SDP offer
        browser_pc = RTCPeerConnection()
        browser_dc = browser_pc.createDataChannel("pcm")
        offer = await browser_pc.createOffer()
        await browser_pc.setLocalDescription(offer)

        result = await adapter.attach_bridge(TEST_BOT_ID, browser_pc.localDescription.sdp)
        await asyncio.sleep(0.3)

        assert "sdp" in result, f"Expected 'sdp' in result, got: {result}"
        assert "error" not in result

        # Cleanup
        await browser_pc.close()

    @pytest.mark.asyncio
    async def test_full_mock_call_lifecycle(self, adapter):
        """Full call lifecycle: outgoing → answer → bridge → audio → end."""
        from aiortc import RTCPeerConnection

        mgr = adapter._get_manager(TEST_BOT_ID)
        _patch_offer(mgr)

        # 1. Start outgoing call
        result = await adapter.start_call(TEST_BOT_ID, TEST_PEER_JID)
        call_id = result["call_id"]
        assert result["state"] == "ringing"

        # 2. Simulate remote accept
        mgr.current_call.apply_transition("remote_accepted")
        mgr.current_call.apply_transition("media_connected")

        # 3. Attach bridge
        browser_pc = RTCPeerConnection()
        browser_dc = browser_pc.createDataChannel("pcm")
        offer = await browser_pc.createOffer()
        await browser_pc.setLocalDescription(offer)

        result = await adapter.attach_bridge(TEST_BOT_ID, browser_pc.localDescription.sdp)
        assert "sdp" in result

        # 4. Feed audio
        pcm = [0.1 * math.sin(2 * math.pi * 440 * i / 16000) for i in range(480)]
        mgr.feed_audio(call_id, pcm)  # Should not crash

        await asyncio.sleep(0.3)

        # 5. End call
        await adapter.end_call(TEST_BOT_ID)

        await browser_pc.close()


class TestVoipAdapterMultipleBots:
    """Test VoipAdapter with multiple bots."""

    @pytest.mark.asyncio
    async def test_two_bots_independent(self):
        adapter = VoipAdapter()
        adapter.start()

        # Register two bots
        mock1 = MockZowsupSocket("bot_A@s.whatsapp.net")
        mock2 = MockZowsupSocket("bot_B@s.whatsapp.net")
        adapter.register_bot("bot_A", mock1)
        adapter.register_bot("bot_B", mock2)

        mgr_a = adapter._get_manager("bot_A")
        mgr_b = adapter._get_manager("bot_B")
        _patch_offer(mgr_a)
        _patch_offer(mgr_b)

        # Start calls independently
        await adapter.start_call("bot_A", "peer_A@s.whatsapp.net")
        await adapter.start_call("bot_B", "peer_B@s.whatsapp.net")

        assert mgr_a.current_call.peer_jid == "peer_A@s.whatsapp.net"
        assert mgr_b.current_call.peer_jid == "peer_B@s.whatsapp.net"

        adapter.stop()
