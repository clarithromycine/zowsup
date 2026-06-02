from ...layers import YowLayer, YowLayerEvent, YowProtocolLayer
from typing import Optional, Any, List, Dict, Union
from .protocolentities import *
class YowPrivacyProtocolLayer(YowProtocolLayer):
    def __init__(self) -> None:
        handleMap = {
            "iq": (self.recvIq, self.sendIq)
        }
        super().__init__(handleMap)

    def __str__(self):
        return "Privacy Layer"

    async def sendIq(self, entity) -> Any:
        if entity.getXmlns() == "jabber:iq:privacy":
            await self.entityToLower(entity)

    def recvIq(self, node) -> Any:        
        pass
