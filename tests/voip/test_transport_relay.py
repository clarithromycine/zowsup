"""
Phase 3 tests — Relay connection and subscriptions.

Tests: SDP modification, RelayConfig, subscription encoding cross-check,
RelayManager structure (without live relay — mock tests).
"""

import sys, os
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pytest
from voip.transport.relay import (
    RelayConfig,
    RelayManager,
    _modify_sdp_for_relay,
    WA_DTLS_FINGERPRINT,
    WA_RELAY_PORT,
)


# Sample SDP (simplified aiortc offer)
SAMPLE_SDP = """v=0
o=- 1234567890 2 IN IP4 127.0.0.1
s=-
t=0 0
a=group:BUNDLE 0
m=application 9 UDP/DTLS/SCTP webrtc-datachannel
c=IN IP4 0.0.0.0
a=ice-ufrag:original_ufrag
a=ice-pwd:original_pwd
a=fingerprint:sha-256 AB:CD:EF:01:23:45:67:89:AB:CD:EF:01:23:45:67:89:AB:CD:EF:01:23:45:67:89:AB:CD:EF:01:23:45
a=setup:actpass
a=mid:0
a=sctp-port:5000
a=max-message-size:262144
a=ice-options:trickle
a=candidate:1 1 udp 2130706431 192.168.1.1 12345 typ host
a=end-of-candidates
"""


class TestSdpModification:
    def test_setup_changed_to_passive(self):
        config = RelayConfig(ip="31.13.100.1", port=3480, token="tok", key="key")
        result = _modify_sdp_for_relay(SAMPLE_SDP, config)
        assert "a=setup:passive" in result
        assert "a=setup:actpass" not in result

    def test_ice_ufrag_replaced(self):
        config = RelayConfig(ip="31.13.100.1", port=3480, auth_token="auth_tok", key="key")
        result = _modify_sdp_for_relay(SAMPLE_SDP, config)
        assert "a=ice-ufrag:auth_tok" in result
        assert "a=ice-ufrag:original_ufrag" not in result

    def test_ice_pwd_replaced(self):
        config = RelayConfig(ip="31.13.100.1", port=3480, token="tok", key="relay_key")
        result = _modify_sdp_for_relay(SAMPLE_SDP, config)
        assert "a=ice-pwd:relay_key" in result

    def test_fingerprint_replaced(self):
        config = RelayConfig(ip="31.13.100.1", port=3480, token="tok", key="key")
        result = _modify_sdp_for_relay(SAMPLE_SDP, config)
        assert f"a=fingerprint:{WA_DTLS_FINGERPRINT}" in result

    def test_relay_candidate_added(self):
        config = RelayConfig(ip="31.13.100.1", port=3480, token="tok", key="key")
        result = _modify_sdp_for_relay(SAMPLE_SDP, config)
        assert "a=candidate:2 1 udp 2122262783 31.13.100.1 3480" in result
        assert "a=end-of-candidates" in result

    def test_ice_options_removed(self):
        config = RelayConfig(ip="31.13.100.1", port=3480, token="tok", key="key")
        result = _modify_sdp_for_relay(SAMPLE_SDP, config)
        assert "ice-options" not in result

    def test_original_candidates_removed(self):
        config = RelayConfig(ip="31.13.100.1", port=3480, token="tok", key="key")
        result = _modify_sdp_for_relay(SAMPLE_SDP, config)
        assert "192.168.1.1 12345" not in result

    def test_fallback_ufrag_to_token(self):
        """When auth_token is empty, fall back to token for ice-ufrag."""
        config = RelayConfig(ip="31.13.100.1", port=3480, token="token_only", key="key")
        result = _modify_sdp_for_relay(SAMPLE_SDP, config)
        assert "a=ice-ufrag:token_only" in result


class TestRelayConfig:
    def test_default_port(self):
        config = RelayConfig(ip="10.0.0.1")
        assert config.port == WA_RELAY_PORT  # 3480

    def test_custom_port(self):
        config = RelayConfig(ip="10.0.0.1", port=9999)
        assert config.port == 9999

    def test_all_fields(self):
        config = RelayConfig(
            ip="31.13.100.1", port=3480,
            token="token_b64", auth_token="auth_b64",
            raw_token=b"raw_tok", raw_auth_token=b"raw_auth",
            key="relay_key", relay_id=5,
            relay_name="relay-us-east", auth_token_id="0",
        )
        assert config.ip == "31.13.100.1"
        assert config.relay_name == "relay-us-east"
        assert config.raw_token == b"raw_tok"
        assert config.relay_id == 5


class TestRelayManager:
    def test_init_state(self):
        mgr = RelayManager()
        assert mgr.has_connection() is False
        assert mgr.connected_count() == 0

    def test_set_ssrc(self):
        mgr = RelayManager()
        mgr.set_ssrc(0x12345678)
        assert mgr._audio_ssrc == 0x12345678

    def test_set_subscription_ssrc(self):
        mgr = RelayManager()
        mgr.set_subscription_ssrc(0xABCDEF01)
        assert mgr._subscription_ssrcs == [0xABCDEF01]

    def test_set_subscription_ssrcs(self):
        mgr = RelayManager()
        mgr.set_subscription_ssrcs([0xAAA, 0xBBB])
        assert mgr._subscription_ssrcs == [0xAAA, 0xBBB]

    def test_set_callbacks(self):
        mgr = RelayManager()
        connected_called = []

        def on_connected():
            connected_called.append(True)

        mgr.set_on_connected(on_connected)
        assert mgr._on_connected is on_connected

        received = []
        mgr.set_on_receive(lambda d: received.append(d))
        assert mgr._on_receive is not None

    def test_broadcast_no_connections(self):
        """Broadcast with no connections should not raise."""
        mgr = RelayManager()
        mgr.broadcast(b"test_data")  # Should not raise

    @pytest.mark.asyncio
    async def test_close_no_connections(self):
        """Close with no connections should not raise."""
        mgr = RelayManager()
        await mgr.close()
