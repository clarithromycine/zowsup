from ...layers import YowProtocolLayer
from typing import Optional, Any, List, Dict, Union
from .protocolentities import *
import logging

logger = logging.getLogger(__name__)

class YowDevicesIqProtocolLayer(YowProtocolLayer):
    def __init__(self) -> None:
        handleMap = {
            "iq": (self.recvIq, self.sendIq),
            "notification": (self.recvNotification, None)
        }
        super().__init__(handleMap)

    def __str__(self):
        return "Device Iq Layer"

    async def recvNotification(self, node) -> Any:

        if node["type"] == "devices":
            if node.getChild("remove"):
                await self.toUpper(RemoveDeviceNotificationProtocolEntity.fromProtocolTreeNode(node))

            elif node.getChild("add"):
                await self.toUpper(AddDeviceNotificationProtocolEntity.fromProtocolTreeNode(node))

            elif node.getChild("update"):
                pass
            else :
                logger.warning("Unsupported device notification type: %s " % node["type"])
                logger.debug("Unsupported device notification node: %s" % node)

    def recvIq(self, node) -> Any:        
        pass

    def sendIq(self, entity) -> Any:
        
        pass
