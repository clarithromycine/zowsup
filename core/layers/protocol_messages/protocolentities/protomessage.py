from .message import MessageProtocolEntity
from typing import Optional, Any, List, Dict, Union
from .proto import ProtoProtocolEntity
from ....layers.protocol_messages.protocolentities.attributes.converter import AttributesConverter
from proto.e2e_pb2 import Message
import logging

logger = logging.getLogger(__name__)

class ProtomessageProtocolEntity(MessageProtocolEntity):
    '''
    <message t="{{TIME_STAMP}}" from="{{CONTACT_JID}}"
        offline="{{OFFLINE}}" type="text" id="{{MESSAGE_ID}}" notify="{{NOTIFY_NAME}}">
            <proto>
                {{SERIALIZE_PROTO_DATA}}
            </proto>
    </message>
    '''
    def __init__(self, messageType, message_attributes, messageMetaAttributes) -> None:
        super().__init__(messageType, messageMetaAttributes)
        self._message_attributes = message_attributes 
        self._raw = None

    def __str__(self):
        out = super().__str__()
        return f"{out}\nmessage_attributes={self._message_attributes}"

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        self._raw  =  AttributesConverter.get().message_to_protobytes(self._message_attributes)
        node.addChild(
            ProtoProtocolEntity(self._raw).toProtocolTreeNode()
        )
        return node

    @property
    def message_attributes(self) -> Any:
        return self._message_attributes

    @message_attributes.setter
    def message_attributes(self, value: Any) -> None:
        self._message_attributes = value

    @property
    def raw(self) -> Any:
        return self._raw

    @raw.setter
    def raw(self, value: Any) -> None:
        self._raw = value        

    @classmethod
    def fromProtocolTreeNode(cls, node):                        
        m = Message()        
        raw = node.getChild("proto").getData()
        m.ParseFromString(raw)              
        entity = MessageProtocolEntity.fromProtocolTreeNode(node,m)
        entity.__class__ = cls
        entity.message_attributes = AttributesConverter.get().proto_to_message(m)

        entity.raw = raw
        return entity
