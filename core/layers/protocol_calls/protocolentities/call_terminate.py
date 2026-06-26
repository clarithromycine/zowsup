
from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes
from core.layers.protocol_calls.protocolentities.with_proto import WithProtoProtocolEntity

from ....structs import ProtocolEntity, ProtocolTreeNode
from .call import CallProtocolEntity
from ....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict
import random
from proto import e2e_pb2
import base64,os


class TerminateCallProtocolEntity(CallProtocolEntity):
    """
    Specialized CallProtocolEntity for "offer" type.
    
    <call from="248846345101511@lid" id="EBC57FE83E0F483E2076A7EB59605470" t="1782399829">
    <terminate call-creator="248846345101511@lid" call-id="007395BF09113DC222E236F72A6D011C" />
    </call>
    """

    def __init__(self,callId=None,callCreator=None,callMetaAttributes=None) -> None:  
        super().__init__("terminate",callCreator=callCreator,callId=callId,callMetaAttributes=callMetaAttributes)


    def __repr__(self):
        return (
            f"TerminateCall(call_id={self.getCallId()}, call_creator={self.call_creator})"
        )

    # ── Deserialization ────────────────────────────────────────

    @staticmethod
    def fromProtocolTreeNode(node: ProtocolTreeNode) -> 'TerminateOffer':
        """Parse a <call> ProtocolTreeNode containing an <offer> child into CallOffer."""
        terminate_node = node.getChild("terminate")
        if terminate_node is None:
            raise ValueError("Not a terminate call: missing <terminate> child")

        call_creator = terminate_node.getAttributeValue("call-creator")
        call_id = terminate_node.getAttributeValue("call-id")

        return TerminateCallProtocolEntity(
            callId=call_id,
            callCreator=call_creator,            
            callMetaAttributes=CallMetaAttributes.from_call_protocoltreenode(node)
        )
