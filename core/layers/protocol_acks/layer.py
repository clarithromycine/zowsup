from ...layers import YowProtocolLayer
from typing import Optional, Any, List, Dict, Union
from .protocolentities import * 
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
        await self.toUpper(IncomingAckProtocolEntity.fromProtocolTreeNode(node))
