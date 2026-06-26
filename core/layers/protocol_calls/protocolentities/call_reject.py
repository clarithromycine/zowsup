
from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes
from core.layers.protocol_calls.protocolentities.with_proto import WithProtoProtocolEntity

from ....structs import ProtocolEntity, ProtocolTreeNode
from .call import CallProtocolEntity
from ....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict
import random
from proto import e2e_pb2
import base64,os


class RejectCallProtocolEntity(CallProtocolEntity):
    """
    Specialized CallProtocolEntity for "offer" type.
    
    <call from="248846345101511@lid" id="93E45CA6563BDD346953A699F70FA85C" t="1782400549">
    <reject call-creator="43775112044544@lid" call-id="00374E9C99DB3ADDE0A0A21DA1750E25" count="0" />
    </call>
    """

    def __init__(self,callId=None,callCreator=None,rejectCount=0,callMetaAttributes=None) -> None:  
        super().__init__("reject",callCreator=callCreator,callId=callId,callMetaAttributes=callMetaAttributes)
        self.rejectCount = rejectCount

    def __repr__(self):
        return (
            f"RejectCall(call_id={self.getCallId()}, call_creator={self.getCallCreator()}, count={self.rejectCount})"
        )

    # ── Deserialization ────────────────────────────────────────

    def toProtocolTreeNode(self) -> ProtocolTreeNode:
        """Override: serialize the full <call> with <offer> children."""
        node = super().toProtocolTreeNode()
        rejectNode = node.getChild("reject")
        rejectNode.setAttribute("count", str(self.rejectCount))
        return node
    
    @staticmethod
    def fromProtocolTreeNode(node: ProtocolTreeNode) -> 'RejectCall':
        """Parse a <call> ProtocolTreeNode containing an <reject> child into RejectCall."""
        reject_node = node.getChild("reject")
        if reject_node is None:
            raise ValueError("Not a reject call: missing <reject> child")

        call_creator = reject_node.getAttributeValue("call-creator")
        call_id = reject_node.getAttributeValue("call-id")
        reject_count_str = reject_node.getAttributeValue("count")
        reject_count = int(reject_count_str) if reject_count_str is not None else 0

        return RejectCallProtocolEntity(
            callId=call_id,
            callCreator=call_creator,     
            rejectCount=reject_count,       
            callMetaAttributes=CallMetaAttributes.from_call_protocoltreenode(node)
        )
