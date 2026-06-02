from ...layers import YowLayer, YowLayerEvent, YowProtocolLayer
from typing import Optional, Any, List, Dict, Union
from .protocolentities import *
from ...layers.protocol_iq.protocolentities import ErrorIqProtocolEntity
class YowPresenceProtocolLayer(YowProtocolLayer):
    def __init__(self) -> None:
        handleMap = {
            "presence": (self.recvPresence, self.sendPresence),
            "iq":       (None, self.sendIq)
        }
        super().__init__(handleMap)

    def __str__(self):
        return "Presence Layer"

    async def sendPresence(self, entity) -> Any:
        await self.entityToLower(entity)

    async def recvPresence(self, node) -> Any:
        await self.toUpper(PresenceProtocolEntity.fromProtocolTreeNode(node))

    async def sendIq(self, entity) -> Any:
        if entity.getXmlns() == LastseenIqProtocolEntity.XMLNS:
            await self._sendIq(entity, self.onLastSeenSuccess, self.onLastSeenError)

    async def onLastSeenSuccess(self, protocolTreeNode, lastSeenEntity) -> Any:
        await self.toUpper(ResultLastseenIqProtocolEntity.fromProtocolTreeNode(protocolTreeNode))

    async def onLastSeenError(self, protocolTreeNode, lastSeenEntity) -> Any:
        await self.toUpper(ErrorIqProtocolEntity.fromProtocolTreeNode(protocolTreeNode))
