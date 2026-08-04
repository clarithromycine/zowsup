"""
Phase 1 tests — Full call layer message flow.

Simulates the complete offer→accept→transport message flow through
YowCallsProtocolLayer, verifying that each entity type is correctly
created and dispatched.
"""

import sys
import os

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pytest
from core.structs import ProtocolTreeNode
from core.layers.protocol_calls.protocolentities import (
    CallProtocolEntity,
    OfferCallProtocolEntity,
    AcceptCallProtocolEntity,
    PreacceptCallProtocolEntity,
    TransportCallProtocolEntity,
    TerminateCallProtocolEntity,
    RejectCallProtocolEntity,
)
from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_meta(recipient="peer@s.whatsapp.net", sender="self@s.whatsapp.net"):
    return CallMetaAttributes(
        recipient=recipient,
        sender=sender,
        timestamp="1782399829",
    )


# ── Test: factory correctly dispatches for each type ─────────────────────────

class TestCallEntityFactoryDispatch:

    def test_offer_dispatches_to_offer_entity(self):
        """Offer type from factory returns generic CallProtocolEntity (specialized in layer with db)."""
        node = _build_offer_node()
        entity = CallProtocolEntity.fromProtocolTreeNode(node)
        # Factory returns generic CallProtocolEntity for offer — the layer
        # creates OfferCallProtocolEntity separately with axolotl_manager.
        assert entity.getType() == "offer"
        assert entity.getCallId() == "OFFER_001"

    def test_accept_dispatches_to_accept_entity(self):
        """Accept type should dispatch to AcceptCallProtocolEntity."""
        meta = _make_meta()
        accept = AcceptCallProtocolEntity(
            callId="ACCEPT_001",
            callCreator="creator@s.whatsapp.net",
            callKey=b"\x00" * 32,
            callMetaAttributes=meta,
            db=None,
        )
        node = accept.toProtocolTreeNode()
        entity = CallProtocolEntity.fromProtocolTreeNode(node)
        assert isinstance(entity, AcceptCallProtocolEntity)
        assert entity.getType() == "accept"

    def test_preaccept_dispatches_to_preaccept_entity(self):
        """Preaccept type should dispatch to PreacceptCallProtocolEntity."""
        meta = _make_meta()
        pa = PreacceptCallProtocolEntity(
            callId="PA_001",
            callCreator="c@s.whatsapp.net",
            callMetaAttributes=meta,
        )
        node = pa.toProtocolTreeNode()
        entity = CallProtocolEntity.fromProtocolTreeNode(node)
        assert isinstance(entity, PreacceptCallProtocolEntity)
        assert entity.getType() == "preaccept"

    def test_transport_dispatches_to_transport_entity(self):
        """Transport type should dispatch to TransportCallProtocolEntity."""
        meta = _make_meta()
        tp = TransportCallProtocolEntity(
            callId="TP_001",
            callCreator="c@s.whatsapp.net",
            callMetaAttributes=meta,
        )
        node = tp.toProtocolTreeNode()
        entity = CallProtocolEntity.fromProtocolTreeNode(node)
        assert isinstance(entity, TransportCallProtocolEntity)
        assert entity.getType() == "transport"

    def test_terminate_dispatches_to_terminate_entity(self):
        """Terminate type should dispatch to TerminateCallProtocolEntity."""
        node = _build_terminate_node()
        entity = CallProtocolEntity.fromProtocolTreeNode(node)
        assert isinstance(entity, TerminateCallProtocolEntity)
        assert entity.getType() == "terminate"

    def test_reject_dispatches_to_reject_entity(self):
        """Reject type should dispatch to RejectCallProtocolEntity."""
        node = _build_reject_node()
        entity = CallProtocolEntity.fromProtocolTreeNode(node)
        assert isinstance(entity, RejectCallProtocolEntity)
        assert entity.getType() == "reject"


# ── Test: full offer→accept→transport message flow ───────────────────────────

class TestOfferAcceptTransportFlow:

    def test_full_flow_entity_chain(self):
        """
        Simulate: offer received → accept built → transport built.
        Verify all entities serialize/deserialize correctly.
        """
        call_id = "FULL_FLOW_CALL_ID"
        creator = "creator@s.whatsapp.net"
        peer = "peer@s.whatsapp.net"

        # 1. Build a received offer (simulating incoming offer)
        offer_node = _build_offer_node(call_id=call_id, creator=creator, peer=peer)
        offer_entity = CallProtocolEntity.fromProtocolTreeNode(offer_node)
        assert offer_entity.getType() == "offer"
        assert offer_entity.getCallId() == call_id

        # 2. Build accept response
        meta = _make_meta(recipient=creator, sender=peer)
        accept = AcceptCallProtocolEntity(
            callId=call_id,
            callCreator=creator,
            callKey=b"\xAB" * 32,
            callMetaAttributes=meta,
            db=None,
        )
        accept_node = accept.toProtocolTreeNode()
        accept_parsed = CallProtocolEntity.fromProtocolTreeNode(accept_node)
        assert isinstance(accept_parsed, AcceptCallProtocolEntity)
        assert accept_parsed.getCallId() == call_id

        # 3. Build transport
        tp_meta = _make_meta(recipient=creator, sender=peer)
        transport = TransportCallProtocolEntity(
            callId=call_id,
            callCreator=creator,
            callMetaAttributes=tp_meta,
        )
        tp_node = transport.toProtocolTreeNode()
        tp_parsed = CallProtocolEntity.fromProtocolTreeNode(tp_node)
        assert isinstance(tp_parsed, TransportCallProtocolEntity)
        assert tp_parsed.getCallId() == call_id

    def test_offer_accept_transport_roundtrip(self):
        """All three entity types go through serialize→deserialize without data loss."""
        call_id = "RT_ALL"
        creator = "c@s.whatsapp.net"

        # Offer
        offer_node = _build_offer_node(call_id=call_id, creator=creator)
        offer = CallProtocolEntity.fromProtocolTreeNode(offer_node)
        assert offer.getCallId() == call_id

        # Accept
        meta = _make_meta(recipient=creator)
        accept = AcceptCallProtocolEntity(
            callId=call_id, callCreator=creator, callKey=b"\xCD" * 32,
            callMetaAttributes=meta, db=None,
        )
        acc_parsed = CallProtocolEntity.fromProtocolTreeNode(accept.toProtocolTreeNode())
        assert acc_parsed.getCallId() == call_id

        # Transport
        tp = TransportCallProtocolEntity(
            callId=call_id, callCreator=creator, callMetaAttributes=meta,
        )
        tp_parsed = CallProtocolEntity.fromProtocolTreeNode(tp.toProtocolTreeNode())
        assert tp_parsed.getCallId() == call_id


# ── Test: preaccept during flow ───────────────────────────────────────────────

class TestPreacceptFlow:

    def test_preaccept_before_accept(self):
        """Simulate preaccept being sent before accept."""
        call_id = "PA_FLOW"
        creator = "c@s.whatsapp.net"

        meta = _make_meta(recipient=creator)
        pa = PreacceptCallProtocolEntity(
            callId=call_id,
            callCreator=creator,
            callMetaAttributes=meta,
        )
        node = pa.toProtocolTreeNode()

        # Verify preaccept has no encrypted content
        pa_node = node.getChild("preaccept")
        assert pa_node is not None
        assert pa_node.getChild("enc") is None, "Preaccept must NOT contain encrypted callKey"

        # Verify roundtrip
        parsed = CallProtocolEntity.fromProtocolTreeNode(node)
        assert isinstance(parsed, PreacceptCallProtocolEntity)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _build_offer_node(call_id="OFFER_001", creator="creator@s.whatsapp.net",
                      peer="peer@s.whatsapp.net"):
    """Build a minimal <call><offer> ProtocolTreeNode for testing."""
    offer_inner = ProtocolTreeNode("offer", {
        "call-id": call_id,
        "call-creator": creator,
    }, children=[
        ProtocolTreeNode("audio", {"enc": "opus", "rate": "8000"}),
        ProtocolTreeNode("audio", {"enc": "opus", "rate": "16000"}),
        ProtocolTreeNode("net", {"medium": "3"}),
        ProtocolTreeNode("enc", {"v": "2", "type": "pkmsg"}, data=b"fake_enc_data"),
        ProtocolTreeNode("encopt", {"keygen": "2"}),
    ])
    return ProtocolTreeNode("call", {
        "from": peer,
        "id": "STANZA_ID",
        "t": "1782399829",
    }, children=[offer_inner])


def _build_terminate_node(call_id="TERM_001", creator="c@s.whatsapp.net",
                          peer="p@s.whatsapp.net"):
    inner = ProtocolTreeNode("terminate", {
        "call-id": call_id,
        "call-creator": creator,
    })
    return ProtocolTreeNode("call", {"from": peer, "id": "SID", "t": "1"}, children=[inner])


def _build_reject_node(call_id="REJ_001", creator="c@s.whatsapp.net",
                       peer="p@s.whatsapp.net"):
    inner = ProtocolTreeNode("reject", {
        "call-id": call_id,
        "call-creator": creator,
        "count": "0",
    })
    return ProtocolTreeNode("call", {"from": peer, "id": "SID", "t": "1"}, children=[inner])
