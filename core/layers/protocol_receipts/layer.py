from ...layers import YowLayer, YowLayerEvent, YowProtocolLayer
from typing import Optional, Any, List, Dict, Union
from .protocolentities import *
class YowReceiptProtocolLayer(YowProtocolLayer):
    def __init__(self) -> None:
        handleMap = {
            "receipt": (self.recvReceiptNode, self.sendReceiptEntity)
        }
        super().__init__(handleMap)

    def __str__(self):
        return "Receipt Layer"

    async def sendReceiptEntity(self, entity) -> Any:
        await self.entityToLower(entity)

    async def recvReceiptNode(self, node) -> Any:
        await self.toUpper(IncomingReceiptProtocolEntity.fromProtocolTreeNode(node))


