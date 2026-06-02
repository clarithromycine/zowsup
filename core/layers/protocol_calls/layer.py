from ...layers import YowProtocolLayer
from typing import Optional, Any, List, Dict, Union
from .protocolentities import *
from ...layers.protocol_acks.protocolentities import OutgoingAckProtocolEntity
from ...layers.protocol_receipts.protocolentities import OutgoingReceiptProtocolEntity
class YowCallsProtocolLayer(YowProtocolLayer):

    def __init__(self) -> None:
        handleMap = {
            "call": (self.recvCall, self.sendCall)
        }
        super().__init__(handleMap)

    def __str__(self):
        return "call Layer"

    async def sendCall(self, entity) -> Any:
        if entity.getTag() == "call":
            await self.toLower(entity.toProtocolTreeNode())

    async def recvCall(self, node) -> Any:
        entity = CallProtocolEntity.fromProtocolTreeNode(node)
        if entity.getType() == "offer":
            receipt = OutgoingReceiptProtocolEntity(node["id"], node["from"], callId = entity.getCallId())
            await self.toLower(receipt.toProtocolTreeNode())
        else:
            ack = OutgoingAckProtocolEntity(node["id"], "call", None, node["from"])
            await self.toLower(ack.toProtocolTreeNode())
        await self.toUpper(entity)

