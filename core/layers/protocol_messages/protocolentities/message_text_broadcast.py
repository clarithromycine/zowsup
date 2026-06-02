from .message_text import TextMessageProtocolEntity
from typing import Optional, Any, List, Dict, Union
from ....structs import ProtocolTreeNode
import time
from .message import MessageMetaAttributes
class BroadcastTextMessage(TextMessageProtocolEntity):
    def __init__(self, bcid, phash,body) -> None:        
        super().__init__(body, message_meta_attributes=MessageMetaAttributes(
            recipient=bcid,
            phash = phash        
        ))
                        
    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = TextMessageProtocolEntity.fromProtocolTreeNode(node)
        return entity
