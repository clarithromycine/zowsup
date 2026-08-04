
from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes
from core.layers.protocol_calls.protocolentities.with_proto import WithProtoProtocolEntity

from ....structs import ProtocolEntity, ProtocolTreeNode
from .call import CallProtocolEntity
from ....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict
import random
from proto import e2e_pb2
import base64,os


class DurationCallProtocolEntity(CallProtocolEntity):
    """
    Specialized CallProtocolEntity for "duration" type.


    这个包是发给服务器的，服务器不用转发给对方，这些信息在terminate包里也有，服务器收到这个包后会更新数据库里的通话时长信息。
    

    <call to='call' id='A47FD628A25E416BCBF667A6B9E61F5A'>
        <duration audio_duration='7203' call-creator='6426:0@lid' peer='1511@lid' call-id='0021DE114DF2B51E4C4DEFBDA371578E' type='1x1'/>
    </call>
    """

    def __init__(self, callId=None, callCreator=None, callMetaAttributes=None,
                 audioduration=None, peer=None, type=None) -> None:
        super().__init__("duration", callCreator=callCreator, callId=callId, callMetaAttributes=callMetaAttributes)
        self.audio_duration = audioduration
        self.peer = peer 
        self.type = type or "1x1"

    def toProtocolTreeNode(self) -> 'ProtocolTreeNode':
        node = super().toProtocolTreeNode()
        duration_node = node.getChild("duration")
        if duration_node:
            if self.audio_duration is not None:
                duration_node.setAttribute("audio_duration", str(self.audio_duration))
            if self.peer is not None:
                duration_node.setAttribute("peer", str(self.peer))
            if self.type is not None:
                duration_node.setAttribute("type", str(self.type))
        return node

    def __repr__(self):
        return (
            f"DurationCall(call_id={self.getCallId()}, call_creator={self.call_creator})"
        )

    # ── Deserialization ────────────────────────────────────────

    @staticmethod
    def fromProtocolTreeNode(node: ProtocolTreeNode) -> 'DurationCallProtocolEntity':
        """Parse a <call> ProtocolTreeNode containing an <duration> child into DurationCallProtocolEntity."""
        duration_node = node.getChild("duration")
        if duration_node is None:
            raise ValueError("Not a duration call: missing <duration> child")

        call_creator = duration_node.getAttributeValue("call-creator")
        call_id = duration_node.getAttributeValue("call-id")
        return DurationCallProtocolEntity(
            callId=call_id,
            callCreator=call_creator,
            audio_duration=int(duration_node.getAttributeValue("audio_duration")),
            peer=duration_node.getAttributeValue("peer"),
            type=duration_node.getAttributeValue("type"),
            callMetaAttributes=CallMetaAttributes.from_call_protocoltreenode(node)
        )

