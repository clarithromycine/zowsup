from ...layers import YowLayer, YowLayerEvent, YowProtocolLayer, IqErrorException
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
            try:
                result_dict = await self.sendIqAsync(entity)
            except IqErrorException as e:
                await self.toUpper(ErrorIqProtocolEntity.fromProtocolTreeNode(e.error_node))
                return
            await self.toUpper(ResultLastseenIqProtocolEntity.fromProtocolTreeNode(result_dict["result"]))
