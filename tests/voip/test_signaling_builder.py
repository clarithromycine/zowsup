"""
Phase 1 tests — VoIP signaling stanza build/parse roundtrip.

Tests for:
- AcceptCallProtocolEntity  (build → serialize → deserialize)
- PreacceptCallProtocolEntity
- TransportCallProtocolEntity
"""

import sys
import os

# Ensure project root on path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pytest
from core.layers.protocol_calls.protocolentities import (
    AcceptCallProtocolEntity,
    PreacceptCallProtocolEntity,
    TransportCallProtocolEntity,
    CallProtocolEntity,
)
from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_meta(recipient="1234567890@s.whatsapp.net", sender="0987654321@s.whatsapp.net"):
    return CallMetaAttributes(
        recipient=recipient,
        sender=sender,
        timestamp="1782399829",
    )


# ── Accept Tests ─────────────────────────────────────────────────────────────

class TestAcceptCallProtocolEntity:
    """Tests for AcceptCallProtocolEntity build/parse roundtrip."""

    def test_build_accept_minimal(self):
        """Build accept stanza with minimal fields (no E2E db)."""
        meta = _make_meta()
        entity = AcceptCallProtocolEntity(
            callId="TEST_CALL_ID_ACCEPT",
            callCreator="creator@s.whatsapp.net",
            callKey=b"\x00" * 32,
            callMetaAttributes=meta,
            db=None,  # No E2E — raw callKey in enc node
        )

        node = entity.toProtocolTreeNode()
        assert node is not None
        assert node.tag == "call"

        accept_node = node.getChild("accept")
        assert accept_node is not None
        assert accept_node.getAttributeValue("call-id") == "TEST_CALL_ID_ACCEPT"
        assert accept_node.getAttributeValue("call-creator") == "creator@s.whatsapp.net"

        # audio
        audio = accept_node.getChild("audio")
        assert audio is not None
        assert audio.getAttributeValue("enc") == "opus"
        assert audio.getAttributeValue("rate") == "16000"

        # net
        net = accept_node.getChild("net")
        assert net is not None
        assert net.getAttributeValue("medium") == "3"

        # enc
        enc = accept_node.getChild("enc")
        assert enc is not None
        assert enc.getAttributeValue("v") == "2"
        assert enc.getAttributeValue("type") in ("msg", "pkmsg")
        assert enc.getData() is not None

        # encopt
        encopt = accept_node.getChild("encopt")
        assert encopt is not None
        assert encopt.getAttributeValue("keygen") == "2"

    def test_accept_roundtrip_no_db(self):
        """Build accept → serialize → deserialize → verify fields (no E2E)."""
        meta = _make_meta()
        entity = AcceptCallProtocolEntity(
            callId="ROUNDTRIP_ACCEPT_ID",
            callCreator="creator@s.whatsapp.net",
            callKey=b"\x01" * 32,
            callMetaAttributes=meta,
            db=None,
        )

        node = entity.toProtocolTreeNode()

        # Parse back via the factory
        parsed = CallProtocolEntity.fromProtocolTreeNode(node)
        assert isinstance(parsed, AcceptCallProtocolEntity)
        assert parsed.getCallId() == "ROUNDTRIP_ACCEPT_ID"
        assert parsed.getCallCreator() == "creator@s.whatsapp.net"
        assert parsed.getNetMedium() == "3"
        assert parsed.getEncoptKeygen() == "2"

    def test_accept_has_required_children(self):
        """Accept stanza must contain audio, net, enc, encopt children."""
        meta = _make_meta()
        entity = AcceptCallProtocolEntity(
            callId="STRUCT_TEST",
            callCreator="creator@s.whatsapp.net",
            callKey=b"\x02" * 32,
            callMetaAttributes=meta,
            db=None,
        )

        node = entity.toProtocolTreeNode()
        accept_node = node.getChild("accept")

        required_tags = ["audio", "net", "enc", "encopt"]
        for tag in required_tags:
            assert accept_node.getChild(tag) is not None, f"Missing <{tag}> in accept"


# ── Preaccept Tests ──────────────────────────────────────────────────────────

class TestPreacceptCallProtocolEntity:
    """Tests for PreacceptCallProtocolEntity build/parse roundtrip."""

    def test_build_preaccept(self):
        """Build preaccept stanza and verify structure."""
        meta = _make_meta()
        entity = PreacceptCallProtocolEntity(
            callId="PREACCEPT_CALL_ID",
            callCreator="creator@s.whatsapp.net",
            netMedium="3",
            callMetaAttributes=meta,
        )

        node = entity.toProtocolTreeNode()
        assert node.tag == "call"

        pa_node = node.getChild("preaccept")
        assert pa_node is not None
        assert pa_node.getAttributeValue("call-id") == "PREACCEPT_CALL_ID"
        assert pa_node.getAttributeValue("call-creator") == "creator@s.whatsapp.net"

        # Must NOT have <enc> (preaccept is unencrypted)
        assert pa_node.getChild("enc") is None

        # Must have capability
        cap = pa_node.getChild("capability")
        assert cap is not None
        assert cap.getAttributeValue("ver") == "1"
        assert cap.getData() is not None

        # Must have encopt
        encopt = pa_node.getChild("encopt")
        assert encopt is not None
        assert encopt.getAttributeValue("keygen") == "2"

    def test_preaccept_roundtrip(self):
        """Build preaccept → serialize → parse back."""
        meta = _make_meta()
        entity = PreacceptCallProtocolEntity(
            callId="PREACCEPT_RT",
            callCreator="creator@s.whatsapp.net",
            callMetaAttributes=meta,
        )

        node = entity.toProtocolTreeNode()
        parsed = CallProtocolEntity.fromProtocolTreeNode(node)
        assert isinstance(parsed, PreacceptCallProtocolEntity)
        assert parsed.getCallId() == "PREACCEPT_RT"
        assert parsed.getCallCreator() == "creator@s.whatsapp.net"


# ── Transport Tests ──────────────────────────────────────────────────────────

class TestTransportCallProtocolEntity:
    """Tests for TransportCallProtocolEntity build/parse roundtrip."""

    def test_build_transport(self):
        """Build transport stanza with default parameters."""
        meta = _make_meta()
        entity = TransportCallProtocolEntity(
            callId="TRANSPORT_CALL_ID",
            callCreator="creator@s.whatsapp.net",
            netMedium="2",
            netProtocol="0",
            transportMessageType="1",
            p2pCandRound="1",
            callMetaAttributes=meta,
        )

        node = entity.toProtocolTreeNode()
        assert node.tag == "call"

        tp_node = node.getChild("transport")
        assert tp_node is not None
        assert tp_node.getAttributeValue("call-id") == "TRANSPORT_CALL_ID"
        assert tp_node.getAttributeValue("call-creator") == "creator@s.whatsapp.net"
        assert tp_node.getAttributeValue("transport-message-type") == "1"
        assert tp_node.getAttributeValue("p2p-cand-round") == "1"

        net = tp_node.getChild("net")
        assert net is not None
        assert net.getAttributeValue("medium") == "2"
        assert net.getAttributeValue("protocol") == "0"

    def test_transport_roundtrip(self):
        """Build transport → serialize → parse back."""
        meta = _make_meta()
        entity = TransportCallProtocolEntity(
            callId="TRANSPORT_RT",
            callCreator="creator@s.whatsapp.net",
            callMetaAttributes=meta,
        )

        node = entity.toProtocolTreeNode()
        parsed = CallProtocolEntity.fromProtocolTreeNode(node)
        assert isinstance(parsed, TransportCallProtocolEntity)
        assert parsed.getCallId() == "TRANSPORT_RT"
        assert parsed.getCallCreator() == "creator@s.whatsapp.net"
        assert parsed.getNetMedium() == "2"


# ── Factory Dispatch Tests ───────────────────────────────────────────────────

class TestFactoryDispatch:
    """Verify CallProtocolEntity.fromProtocolTreeNode dispatches correctly."""

    def test_accept_type_dispatches(self):
        meta = _make_meta()
        entity = AcceptCallProtocolEntity(
            callId="DISPATCH_ACCEPT",
            callCreator="c@s.whatsapp.net",
            callKey=b"\x03" * 32,
            callMetaAttributes=meta,
            db=None,
        )
        parsed = CallProtocolEntity.fromProtocolTreeNode(entity.toProtocolTreeNode())
        assert isinstance(parsed, AcceptCallProtocolEntity)
        assert parsed.getType() == "accept"

    def test_preaccept_type_dispatches(self):
        meta = _make_meta()
        entity = PreacceptCallProtocolEntity(
            callId="DISPATCH_PA",
            callCreator="c@s.whatsapp.net",
            callMetaAttributes=meta,
        )
        parsed = CallProtocolEntity.fromProtocolTreeNode(entity.toProtocolTreeNode())
        assert isinstance(parsed, PreacceptCallProtocolEntity)
        assert parsed.getType() == "preaccept"

    def test_transport_type_dispatches(self):
        meta = _make_meta()
        entity = TransportCallProtocolEntity(
            callId="DISPATCH_TP",
            callCreator="c@s.whatsapp.net",
            callMetaAttributes=meta,
        )
        parsed = CallProtocolEntity.fromProtocolTreeNode(entity.toProtocolTreeNode())
        assert isinstance(parsed, TransportCallProtocolEntity)
        assert parsed.getType() == "transport"
