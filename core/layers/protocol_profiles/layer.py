from ...layers import  YowProtocolLayer
from typing import Optional, Any, List, Dict, Union
from .protocolentities import *
from ...layers.protocol_iq.protocolentities import ErrorIqProtocolEntity, ResultIqProtocolEntity
class YowProfilesProtocolLayer(YowProtocolLayer):
    def __init__(self) -> None:
        handleMap = {
            "iq": (self.recvIq, self.sendIq)
        }
        super().__init__(handleMap)

    def __str__(self):
        return "Profiles Layer"

    async def sendIq(self, entity) -> Any:
        if entity.getXmlns() == "w:profile:picture":
            node =     entity.toProtocolTreeNode()    
            await self.toLower(node)
        #elif entity.getXmlns() == "privacy":
        #    self._sendIq(entity, self.onPrivacyResult, self.onPrivacyError)
        elif isinstance(entity, GetStatusesIqProtocolEntity):
            await self._sendIq(entity)
        elif isinstance(entity, SetStatusIqProtocolEntity):
            await self._sendIq(entity)

    def recvIq(self, node) -> Any:        
        pass




    


