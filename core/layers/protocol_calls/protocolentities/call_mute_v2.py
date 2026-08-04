
from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes
from core.layers.protocol_calls.protocolentities.with_proto import WithProtoProtocolEntity

from ....structs import ProtocolEntity, ProtocolTreeNode
from .call import CallProtocolEntity
from ....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict
import random
from proto import e2e_pb2
import base64,os


class MuteV2CallProtocolEntity(CallProtocolEntity):
    """
    Specialized CallProtocolEntity for "terminate" type.
    

    <call from='1511@lid' id='02C4F5D9CA193B6C808BC3D28FE814C1' t='1782961942'>
         <mute_v2 mute-state='0' call-creator='6426@lid' call-id='0021DE114DF2B51E4C4DEFBDA371578E'/>
    </call>
    """

    def __init__(self, callId=None, callCreator=None, callMetaAttributes=None, muteState=None) -> None:
        super().__init__("mute_v2", callCreator=callCreator, callId=callId, callMetaAttributes=callMetaAttributes)
        self.mute_state = muteState if muteState is not None else "0"

    def toProtocolTreeNode(self) -> 'ProtocolTreeNode':
        node = super().toProtocolTreeNode()
        mute_v2_node = node.getChild("mute_v2")
        if mute_v2_node:
            if self.mute_state is not None:
                mute_v2_node.setAttribute("mute-state", str(self.mute_state))  
        return node

    def __repr__(self):
        return (
            f"MuteV2Call(call_id={self.getCallId()}, call_creator={self.call_creator})"
        )

    # ── Deserialization ────────────────────────────────────────

    @staticmethod
    def fromProtocolTreeNode(node: ProtocolTreeNode) -> 'MuteV2CallProtocolEntity':
        """Parse a <call> ProtocolTreeNode containing an <mute_v2> child into MuteV2CallProtocolEntity."""
        mute_v2_node = node.getChild("mute_v2")
        if mute_v2_node is None:
            raise ValueError("Not a mute_v2 call: missing <mute_v2> child")

        call_creator = mute_v2_node.getAttributeValue("call-creator")
        call_id = mute_v2_node.getAttributeValue("call-id")
        mute_state = mute_v2_node.getAttributeValue("mute-state")

        return MuteV2CallProtocolEntity(
            callId=call_id,
            callCreator=call_creator,
            muteState=mute_state,
            callMetaAttributes=CallMetaAttributes.from_call_protocoltreenode(node)
        )
