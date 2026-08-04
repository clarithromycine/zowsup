"""
TransportCallProtocolEntity - <call><transport> stanza entity.

Sent after accept to trigger the peer to send relay endpoint information,
and to convey media transport parameters.

<call to="peer@s.whatsapp.net" id="STANZA_ID">
  <transport call-id="CALL_ID" call-creator="creator"
             transport-message-type="1" p2p-cand-round="0">
    <net medium="2" protocol="0"/>
  </transport>
</call>

Reference: WaCalls internal/voip/call/callmanager_signaling.go HandleCallAccept()
"""

from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes
from ....structs import ProtocolTreeNode
from .call import CallProtocolEntity
from typing import Optional


class TransportCallProtocolEntity(CallProtocolEntity):
    """
    Specialized CallProtocolEntity for "transport" type.

    Carries network medium and protocol for media transport negotiation.
    """

    def __init__(
        self,
        callId: Optional[str] = None,
        callCreator: Optional[str] = None,
        netMedium: Optional[str] = None,
        netProtocol: Optional[str] = None,
        transportMessageType: Optional[str] = None,
        p2pCandRound: Optional[str] = None,
        rte: Optional[bytes] = None,
        te_candidates: Optional[list] = None,
        callMetaAttributes: Optional[CallMetaAttributes] = None,
    ) -> None:
        super().__init__("transport", callCreator=callCreator, callId=callId, callMetaAttributes=callMetaAttributes)

        self.netMedium = netMedium or "2"
        self.netProtocol = netProtocol or "0"
        self.transportMessageType = transportMessageType or "1"
        self.p2pCandRound = p2pCandRound or "1"
        self.rte = rte  # raw bytes for <rte> child (relay token exchange)
        self.te_candidates = te_candidates or []  # list[dict]: {"priority":int, "data":bytes}

    def __repr__(self):
        return (
            f"TransportCall(call_id={self.getCallId()}, call_creator={self.getCallCreator()}, "
            f"net_medium={self.netMedium}, net_protocol={self.netProtocol})"
        )

    # ── Accessors ──────────────────────────────────────────────

    def getNetMedium(self) -> Optional[str]:
        return self.netMedium

    def getNetProtocol(self) -> Optional[str]:
        return self.netProtocol

    def getTransportMessageType(self) -> Optional[str]:
        return self.transportMessageType

    def getP2pCandRound(self) -> Optional[str]:
        return self.p2pCandRound

    # ── Serialization ──────────────────────────────────────────

    def toProtocolTreeNode(self) -> ProtocolTreeNode:
        node = super().toProtocolTreeNode()
        transportNode = node.getChild("transport")

        if self.transportMessageType is not None:
            transportNode.setAttribute("transport-message-type", self.transportMessageType)
        if self.p2pCandRound is not None:
            transportNode.setAttribute("p2p-cand-round", self.p2pCandRound)

        net_attrs = {"medium": self.netMedium}
        if self.netProtocol is not None:
            net_attrs["protocol"] = self.netProtocol
        children = [ProtocolTreeNode("net", net_attrs)]
        if self.rte:
            children.append(ProtocolTreeNode("rte", data=bytes(self.rte)))
        # Include <te> P2P candidates
        for te in self.te_candidates or []:
            children.append(ProtocolTreeNode("te", {"priority": str(te["priority"])}, data=te["data"]))
        transportNode.addChildren(children)
        return node

    # ── Deserialization ────────────────────────────────────────

    @staticmethod
    def fromProtocolTreeNode(node: ProtocolTreeNode) -> "TransportCallProtocolEntity":
        transport_node = node.getChild("transport")
        if transport_node is None:
            raise ValueError("Not a transport call: missing <transport> child")

        call_creator = transport_node.getAttributeValue("call-creator")
        call_id = transport_node.getAttributeValue("call-id")
        transport_msg_type = transport_node.getAttributeValue("transport-message-type")
        p2p_cand_round = transport_node.getAttributeValue("p2p-cand-round")

        net_medium = None
        net_protocol = None
        net_node = transport_node.getChild("net")
        if net_node:
            net_medium = net_node.getAttributeValue("medium")
            net_protocol = net_node.getAttributeValue("protocol")

        # Parse <rte>
        rte_data = None
        rte_node = transport_node.getChild("rte")
        if rte_node:
            rte_data = rte_node.getData()

        # Parse <te> P2P candidates (6-byte IP:port addresses)
        te_candidates = []
        import base64
        for te_node in transport_node.getAllChildren("te"):
            priority = te_node.getAttributeValue("priority")
            te_data = te_node.getData()
            if te_data:
                try:
                    raw = base64.b64decode(te_data) if isinstance(te_data, str) else te_data
                except Exception:
                    raw = te_data if isinstance(te_data, bytes) else b""
                if 6 <= len(raw) <= 18:
                    te_candidates.append({
                        "priority": int(priority) if priority else 0,
                        "data": raw,
                    })

        return TransportCallProtocolEntity(
            callId=call_id,
            callCreator=call_creator,
            netMedium=net_medium,
            netProtocol=net_protocol,
            transportMessageType=transport_msg_type,
            p2pCandRound=p2p_cand_round,
            rte=rte_data,
            te_candidates=te_candidates,
            callMetaAttributes=CallMetaAttributes.from_call_protocoltreenode(node),
        )
