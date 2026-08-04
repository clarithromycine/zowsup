"""
RelayLatencyCallProtocolEntity - <call><relaylatency> stanza entity.

Reports relay RTT measurements to the peer.

<call to="peer@s.whatsapp.net" id="STANZA_ID">
  <relaylatency call-id="CALL_ID" call-creator="creator">
    <te latency="33554432" relay_name="sin6c01">0x9df0d13e0d96</te>
    <destination><to jid="..."/></destination>  <!-- optional -->
  </relaylatency>
</call>
"""

from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes
from ....structs import ProtocolTreeNode
from .call import CallProtocolEntity
from typing import Optional, List, Dict


class RelayLatencyCallProtocolEntity(CallProtocolEntity):
    """
    Specialized CallProtocolEntity for "relaylatency" type.

    Carries relay latency measurements (<te> elements) and optional
    <destination> targeting.
    """

    def __init__(
        self,
        callId: Optional[str] = None,
        callCreator: Optional[str] = None,
        te_entries: Optional[List[Dict]] = None,
        destination_jids: Optional[List[str]] = None,
        callMetaAttributes: Optional[CallMetaAttributes] = None,
    ) -> None:
        super().__init__("relaylatency", callCreator=callCreator, callId=callId, callMetaAttributes=callMetaAttributes)
        self.te_entries = te_entries or []
        self.destination_jids = destination_jids or []

    def __repr__(self):
        return (
            f"RelayLatency(call_id={self.getCallId()}, call_creator={self.getCallCreator()}, "
            f"te_count={len(self.te_entries)})"
        )

    # ── Serialization ──────────────────────────────────────────

    def toProtocolTreeNode(self) -> ProtocolTreeNode:
        node = super().toProtocolTreeNode()
        rl_node = node.getChild("relaylatency")
        if rl_node is None:
            return node

        # Add <te> elements
        for entry in self.te_entries:
            te = ProtocolTreeNode(
                "te",
                {"latency": str(entry["latency"]), "relay_name": entry["relay_name"]},
                data=entry.get("data", b""),
            )
            rl_node.addChild(te)

        # Optional <destination>
        if self.destination_jids:
            dest = ProtocolTreeNode("destination")
            for jid in self.destination_jids:
                dest.addChild(ProtocolTreeNode("to", {"jid": jid}))
            rl_node.addChild(dest)

        return node

    # ── Deserialization ────────────────────────────────────────

    @staticmethod
    def fromProtocolTreeNode(node: ProtocolTreeNode) -> "RelayLatencyCallProtocolEntity":
        rl_node = node.getChild("relaylatency")
        if rl_node is None:
            raise ValueError("Not a relaylatency call: missing <relaylatency> child")

        call_creator = rl_node.getAttributeValue("call-creator")
        call_id = rl_node.getAttributeValue("call-id")

        te_entries = []
        for te_node in rl_node.getAllChildren("te"):
            te_entries.append({
                "latency": te_node.getAttributeValue("latency"),
                "relay_name": te_node.getAttributeValue("relay_name"),
                "data": te_node.getData() or b"",
            })

        destination_jids = []
        dest_node = rl_node.getChild("destination")
        if dest_node:
            for to_node in dest_node.getAllChildren("to"):
                jid = to_node.getAttributeValue("jid")
                if jid:
                    destination_jids.append(jid)

        return RelayLatencyCallProtocolEntity(
            callId=call_id,
            callCreator=call_creator,
            te_entries=te_entries,
            destination_jids=destination_jids,
            callMetaAttributes=CallMetaAttributes.from_call_protocoltreenode(node),
        )