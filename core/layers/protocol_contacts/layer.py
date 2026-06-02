from ...layers import YowProtocolLayer
from typing import Optional, Any, List, Dict, Union
from .protocolentities import *
import logging

logger = logging.getLogger(__name__)


class YowContactsIqProtocolLayer(YowProtocolLayer):
    def __init__(self) -> None:
        handleMap = {
            "iq": (self.recvIq, self.sendIq),
            "notification": (self.recvNotification, None)
        }
        super().__init__(handleMap)

    def __str__(self):
        return "Contact Iq Layer"

    async def recvNotification(self, node) -> Any:

        if node["type"] == "contacts":
            if node.getChild("remove"):
                await self.toUpper(RemoveContactNotificationProtocolEntity.fromProtocolTreeNode(node))

            elif node.getChild("add"):
                await self.toUpper(AddContactNotificationProtocolEntity.fromProtocolTreeNode(node))

            elif node.getChild("update"):
                await self.toUpper(UpdateContactNotificationProtocolEntity.fromProtocolTreeNode(node))

            elif node.getChild("usync"):
                await self.toUpper(ContactsSyncNotificationProtocolEntity.fromProtocolTreeNode(node))

            else:
                logger.warning("Unsupported contact notification type: %s " % node["type"])
                logger.debug("Unsupported contact notification node: %s" % node)

    async def recvIq(self, node) -> Any:        
        if node["type"] == "result":            
            usyncNode = node.getChild("usync")
            if usyncNode:            

                if usyncNode["context"]=="interactive" or usyncNode["context"]=="registration":
                    entity = ContactResultSyncIqProtocolEntity.fromProtocolTreeNode(node)            
                    await self.toUpper(entity)     

                if usyncNode["context"] == "message" and usyncNode.getAttributeValue("mode") == "query":
                    resultNode = usyncNode.getChild("result")
                    hasDevices = bool(resultNode and resultNode.getChild("devices"))

                    if hasDevices:
                        entity = DevicesResultSyncIqProtocolEntity.fromProtocolTreeNode(node)
                        await self.toUpper(entity)
                    else:
                        entity = ProfilesResultSyncIqProtocolEntity.fromProtocolTreeNode(node)  
                        await self.toUpper(entity)

                    
    async def sendIq(self, entity) -> Any:
        if entity.getXmlns() == "usync":
            node = entity.toProtocolTreeNode()            
            await self.toLower(node)        
