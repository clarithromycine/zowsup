"""
Phase 1 tests — Relay ack parser and CallNodeInfo extraction.

Tests for:
- parse_relay_from_ack() — structured relay ack parsing
- extract_relay_endpoints() — attribute and structured format
- extract_node_info() — call stanza metadata extraction
"""

import sys
import os

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import base64
import pytest
from core.structs import ProtocolTreeNode
from voip.signaling import RelayEndpoint, ParsedRelayAck, CallNodeInfo
from voip.signaling.parser import (
    extract_node_info,
    extract_relay_endpoints,
    parse_relay_from_ack,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_call_node(tag="offer", call_id="TEST_CALL_ID", call_creator="creator@s.whatsapp.net",
                    from_jid="peer@s.whatsapp.net"):
    """Build a minimal <call> ProtocolTreeNode for testing."""
    inner = ProtocolTreeNode(tag, {"call-id": call_id, "call-creator": call_creator})
    return ProtocolTreeNode("call", {"from": from_jid, "id": "STANZA_ID", "t": "1782399829"},
                            children=[inner])


# ── extract_node_info tests ──────────────────────────────────────────────────

class TestExtractNodeInfo:

    def test_extract_offer_info(self):
        node = _make_call_node(tag="offer", call_id="OFFER_001",
                               call_creator="creator@s.whatsapp.net",
                               from_jid="peer@s.whatsapp.net")
        info = extract_node_info(node)
        assert info is not None
        assert info.tag == "offer"
        assert info.call_id == "OFFER_001"
        assert info.peer_jid == "peer@s.whatsapp.net"
        assert info.call_creator == "creator@s.whatsapp.net"

    def test_extract_accept_info(self):
        node = _make_call_node(tag="accept", call_id="ACCEPT_001",
                               call_creator="creator@s.whatsapp.net")
        info = extract_node_info(node)
        assert info.tag == "accept"
        assert info.call_id == "ACCEPT_001"

    def test_extract_transport_info(self):
        node = _make_call_node(tag="transport", call_id="TP_001",
                               call_creator="creator@s.whatsapp.net")
        info = extract_node_info(node)
        assert info.tag == "transport"

    def test_none_node_returns_none(self):
        assert extract_node_info(None) is None


# ── extract_relay_endpoints tests ────────────────────────────────────────────

class TestExtractRelayEndpoints:

    def test_extract_attribute_format(self):
        """Parse relay endpoints in attribute format: <relay ip="x" token="y" port="z"/>"""
        # extract_relay_endpoints receives the inner node (e.g., offer child)
        inner = ProtocolTreeNode("offer", {"call-id": "C1", "call-creator": "c@s.whatsapp.net"}, children=[
            ProtocolTreeNode("relay", {"ip": "31.13.100.1", "token": "token_abc", "port": "3480",
                                       "relay-key": "key123"}),
            ProtocolTreeNode("relay", {"ip": "31.13.100.2", "token": "token_def", "port": "3480"}),
        ])

        relays = extract_relay_endpoints(inner)
        assert len(relays) == 2
        assert relays[0].ip == "31.13.100.1"
        assert relays[0].port == 3480
        assert relays[0].token == "token_abc"
        assert relays[0].key == "key123"
        assert relays[1].ip == "31.13.100.2"

    def test_extract_empty(self):
        """Node with no relay children returns empty list."""
        node = _make_call_node()
        info = extract_node_info(node)
        relays = extract_relay_endpoints(info.inner_node)
        assert relays == []

    def test_extract_relays_wrapper(self):
        """Parse <relays><relay .../></relays> wrapper format."""
        inner = ProtocolTreeNode("offer", {"call-id": "C1", "call-creator": "c@s.whatsapp.net"}, children=[
            ProtocolTreeNode("relays", children=[
                ProtocolTreeNode("relay", {"ip": "31.13.100.3", "token": "tok3", "port": "3480"}),
            ]),
        ])
        relays = extract_relay_endpoints(inner)
        assert len(relays) == 1
        assert relays[0].ip == "31.13.100.3"


# ── parse_relay_from_ack tests ───────────────────────────────────────────────

class TestParseRelayFromAck:

    def test_parse_structured_relay_te2_format(self):
        """Parse the full structured relay ack with te2 endpoints."""
        relay_key = b"test_relay_key_32_bytes_xxxxxx"
        token_bytes = b"raw_token_bytes_123456789"
        auth_token_bytes = b"raw_auth_token_bytes_123456"

        # parse_relay_from_ack receives the <offer> node directly (not <iq>)
        ack_node = ProtocolTreeNode("offer", {"call-id": "CALL_ID"}, children=[
            ProtocolTreeNode("relay", {"uuid": "session-uuid-123", "self_pid": "1", "peer_pid": "2"}, children=[
                ProtocolTreeNode("key", data=relay_key),
                ProtocolTreeNode("token", {"id": "0"}, data=token_bytes),
                ProtocolTreeNode("auth_token", {"id": "0"}, data=auth_token_bytes),
                ProtocolTreeNode("te2", {
                    "token_id": "0", "auth_token_id": "0",
                    "relay_name": "relay-us-east",
                }, data=b"\x1f\x0d\x64\x0a\x0d\x98"),  # 31.13.100.10:3480
                ProtocolTreeNode("te2", {
                    "token_id": "0", "auth_token_id": "0",
                    "relay_name": "relay-us-west",
                }, data=b"\x1f\x0d\x64\x0b\x0d\x98"),  # 31.13.100.11:3480
                ProtocolTreeNode("participant", {"jid": "sender:0@s.whatsapp.net"}),
                ProtocolTreeNode("participant", {"jid": "recipient:0@s.whatsapp.net"}),
            ]),
        ])

        result = parse_relay_from_ack(ack_node)

        assert result.uuid == "session-uuid-123"
        assert result.self_pid == 1
        assert result.peer_pid == 2
        assert len(result.relays) == 2
        assert result.relays[0].ip == "31.13.100.10"
        assert result.relays[0].port == 3480
        assert result.relays[0].relay_name == "relay-us-east"
        assert result.relays[0].token != ""  # base64 encoded
        assert result.relays[0].raw_token == token_bytes
        assert result.relays[0].auth_token != ""
        assert result.relays[0].raw_auth_token == auth_token_bytes
        assert result.relays[1].ip == "31.13.100.11"
        assert result.relays[1].relay_name == "relay-us-west"
        assert len(result.participant_jids) == 2
        assert "sender:0@s.whatsapp.net" in result.participant_jids
        assert "recipient:0@s.whatsapp.net" in result.participant_jids

    def test_parse_hbh_key(self):
        """Parse 30-byte hop-by-hop key from relay ack."""
        hbh = b"\x01" * 30
        ack_node = ProtocolTreeNode("offer", {"call-id": "C1"}, children=[
            ProtocolTreeNode("relay", {"uuid": "u1"}, children=[
                ProtocolTreeNode("key", data=b"relay_key"),
                ProtocolTreeNode("hbh_key", data=hbh),
                ProtocolTreeNode("token", {"id": "0"}, data=b"tok"),
                ProtocolTreeNode("te2", children=[
                    ProtocolTreeNode("te", {"ip": "1.2.3.4", "port": "3480"}),
                ]),
            ]),
        ])

        result = parse_relay_from_ack(ack_node)
        assert result.hbh_key == hbh

    def test_parse_user_device_participants(self):
        """Extract participants from <user><device jid="..."> nodes."""
        ack_node = ProtocolTreeNode("iq", {"type": "result"}, children=[
            ProtocolTreeNode("user", children=[
                ProtocolTreeNode("device", {"jid": "device1@s.whatsapp.net"}),
                ProtocolTreeNode("device", {"jid": "device2@s.whatsapp.net"}),
            ]),
        ])

        result = parse_relay_from_ack(ack_node)
        assert "device1@s.whatsapp.net" in result.participant_jids
        assert "device2@s.whatsapp.net" in result.participant_jids

    def test_parse_empty_ack(self):
        """Empty ack returns default ParsedRelayAck."""
        node = ProtocolTreeNode("iq", {"type": "result"})
        result = parse_relay_from_ack(node)
        assert result.relays == []
        assert result.uuid == ""
        assert result.self_pid is None
