#from .protomessage import ProtomessageProtocolEntity
from .message import MessageMetaAttributes
from typing import Optional, Any, List, Dict, Union
from .attributes.attributes_message import MessageAttributes
from .protomessage import ProtomessageProtocolEntity
from proto.e2e_pb2 import Message
from .message import MessageProtocolEntity
from .message_extendedtext import ExtendedTextMessageProtocolEntity
from .message_protocol import ProtocolMessageProtocolEntity
from ....layers.protocol_messages.protocolentities.attributes.converter import AttributesConverter

class TextMessageProtocolEntity(ProtomessageProtocolEntity):
    def __init__(self, body, message_meta_attributes=None,to=None) -> None:
        # flexible attributes for temp backwards compat
        assert(bool(message_meta_attributes) ^ bool(to)), "Either set message_meta_attributes, or to, and not both"
        if to:
            message_meta_attributes = MessageMetaAttributes(recipient=to)
                                    
        super().__init__("text", MessageAttributes(conversation = body), message_meta_attributes)
        self.setBody(body)

    @property
    def conversation(self) -> Any:
        return self.message_attributes.conversation

    @conversation.setter
    def conversation(self, value: Any) -> None:
        self.message_attributes.conversation = value

    def getBody(self) -> Any:
        #obsolete
        return self.conversation

    def setBody(self, body) -> Any:
        #obsolete
        self.conversation = body

    @classmethod
    def fromProtocolTreeNode(cls, node):
    
        #这里智能判断类型， 可能是 TextMessageProtocolEntity 也可能是 ExtendedTextMessageProtocolEntity

        #所以不走原来的 ProtomessageProtocolEntity.fromProtocolTreeNode

        entity = ProtomessageProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = cls

        if entity.message_attributes.extended_text is not None:
            entity.__class__ = ExtendedTextMessageProtocolEntity

        elif entity.conversation is not None:
            entity.__class__ = TextMessageProtocolEntity

        else:
            #hist_sync 走这里            
            entity.__class__ = ProtocolMessageProtocolEntity
                
        return entity
