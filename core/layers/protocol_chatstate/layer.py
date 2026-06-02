from ...layers import YowLayer, YowLayerEvent, YowProtocolLayer
from typing import Optional, Any, List, Dict, Union
from .protocolentities import * 
class YowChatstateProtocolLayer(YowProtocolLayer):
    def __init__(self) -> None:
        handleMap = {
            "chatstate": (self.recvChatstateNode, self.sendChatstateEntity)
        }
        super().__init__(handleMap)

    def __str__(self):
        return "Chatstate Layer"

    async def sendChatstateEntity(self, entity) -> Any:
        await self.entityToLower(entity)

    async def recvChatstateNode(self, node) -> Any:
        await self.toUpper(IncomingChatstateProtocolEntity.fromProtocolTreeNode(node))
