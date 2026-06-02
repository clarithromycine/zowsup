from .protomessage import ProtomessageProtocolEntity
from typing import Optional, Any, List, Dict, Union
from .message import MessageMetaAttributes
from .attributes.attributes_message import MessageAttributes
from proto import e2e_pb2
from .message import MessageProtocolEntity
from .message_poll_creation import PollCreationMessageProtocolEntity
from ....layers.protocol_messages.protocolentities.attributes.converter import AttributesConverter

class PollUpdateMessageProtocolEntity(ProtomessageProtocolEntity):
    def __init__(self,poll_update_attr,message_meta_attributes=None, to=None) -> None:
        
        assert(bool(message_meta_attributes) ^ bool(to)), "Either set message_meta_attributes, or to, and not both"        
        if to:
            message_meta_attributes = MessageMetaAttributes(recipient=to)

        super().__init__("poll", MessageAttributes(poll_update = poll_update_attr), message_meta_attributes)


    @classmethod
    def fromProtocolTreeNode(cls, node, message_db):

        m = e2e_pb2.Message()        
        raw = node.getChild("proto").getData()
        m.ParseFromString(raw)              

        entity = MessageProtocolEntity.fromProtocolTreeNode(node,m)
        if m.HasField("pollCreationMessageV3") :        
            entity.__class__ = PollCreationMessageProtocolEntity

        if m.HasField("poll_update_message") :
            entity.__class__ = PollUpdateMessageProtocolEntity

        entity.message_attributes = AttributesConverter.get().proto_to_message(m,from_jid=node.getAttributeValue("from"),message_db=message_db)
        
        entity.raw = raw
        return entity