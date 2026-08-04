from ...layers import YowProtocolLayer
from typing import Optional, Any, List, Dict, Union
from .protocolentities import * 
import logging
logger = logging.getLogger(__name__)

class YowAckProtocolLayer(YowProtocolLayer):
    def __init__(self) -> None:
        handleMap = {
            "ack": (self.recvAckNode, self.sendAckEntity)
        }
        super().__init__(handleMap)

    def __str__(self):
        return "Ack Layer"

    async def sendAckEntity(self, entity) -> Any:
        await self.entityToLower(entity)

    async def recvAckNode(self, node) -> Any:
        logger.debug("ACK LAYER recv: id=%s class=%s type=%s children=%d",
                     node.getAttributeValue("id"),
                     node.getAttributeValue("class"),
                     node.getAttributeValue("type"),
                     len(getattr(node, "children", []) or []))
        await self.toUpper(IncomingAckProtocolEntity.fromProtocolTreeNode(node))
