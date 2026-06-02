from ...layers import YowProtocolLayer
from typing import Optional, Any, List, Dict, Union
from .protocolentities import *
from ...layers.protocol_messages.protocolentities.attributes.converter import AttributesConverter
from ...layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from ...layers.protocol_receipts.protocolentities import OutgoingReceiptProtocolEntity
from ...layers.protocol_acks.protocolentities import OutgoingAckProtocolEntity

import logging
logger = logging.getLogger(__name__)


class YowMessagesProtocolLayer(YowProtocolLayer):
    def __init__(self) -> None:
        handleMap = {
            "message": (self.recvMessageStanza, self.sendMessageEntity)
        }
        super().__init__(handleMap)

    def __str__(self):
        return "Messages Layer"

    async def sendMessageEntity(self, entity) -> Any:        
        if entity.getType() in ["text","poll"]:                              
            await self.entityToLower(entity)

    ###recieved node handlers handlers    
    async def recvMessageStanza(self, node) -> Any:            

        if node.getAttributeValue("from").endswith("@newsletter"):
            await self.toLower(OutgoingReceiptProtocolEntity(
                            messageIds=[node["id"]],
                            to=node["from"],
                            view=True,
                            serverIds=node["server_id"]
                        ).toProtocolTreeNode())    
            return               
         
        protoNode = node.getChild("proto")                                
        if protoNode is None :
            return
        
        
        if node.getAttributeValue("type")=="reaction":
            entity = ReactionMessageProtocolEntity.fromProtocolTreeNode(node)
            await self.toUpper(entity)
        
        elif node.getAttributeValue("type")=="poll":                               
            entity = PollUpdateMessageProtocolEntity.fromProtocolTreeNode(node,message_db = self.getStack().getProp("profile").axolotl_manager )
            await self.toUpper(entity)
            
 
        elif node.getAttributeValue("type")=="text":                       
            entity = TextMessageProtocolEntity.fromProtocolTreeNode(node)                                  
            await self.toUpper(entity)

