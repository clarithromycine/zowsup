from ...common import YowConstants
from typing import Optional, Any, List, Dict, Union
from ...layers import YowLayerEvent, YowProtocolLayer, EventCallback
from ...layers.network import YowNetworkLayer
from .protocolentities import *
from .layer_interface_authentication import YowAuthenticationProtocolLayerInterface
from .protocolentities import StreamErrorProtocolEntity
import logging

logger = logging.getLogger(__name__)


class YowAuthenticationProtocolLayer(YowProtocolLayer):
    EVENT_AUTHED  = "org.openwhatsapp.zowsup.event.auth.authed"
    EVENT_AUTH = "org.openwhatsapp.zowsup.event.auth"
    PROP_CREDENTIALS = "org.openwhatsapp.zowsup.prop.auth.credentials"
    PROP_PASSIVE = "org.openwhatsapp.zowsup.prop.auth.passive"    

    def __init__(self) -> None:
        handleMap = {
            "stream:features": (self.handleStreamFeatures, None),
            "failure": (self.handleFailure, None),
            "success": (self.handleSuccess, None),
            #"w:p": (self.handleSuccess, None),
            "stream:error": (self.handleStreamError, None),            
        }
        super().__init__(handleMap)
        self.interface = YowAuthenticationProtocolLayerInterface(self)

    def __str__(self):
        return "Authentication Layer"

    @EventCallback(YowNetworkLayer.EVENT_STATE_CONNECTED)
    async def on_connected(self, event) -> Any:                   
        await self.broadcastEvent(
            YowLayerEvent(
                self.EVENT_AUTH,
                passive=self.getProp(self.PROP_PASSIVE, False)
            )
        )
        

    def setCredentials(self, credentials) -> Any:
        logger.warning("setCredentials is deprecated and has no effect, user stack.setProfile instead")

    def getUsername(self, full = False) -> Any:
        username = self.getProp("profile").username
        return username if not full else (f"{username}@{YowConstants.WHATSAPP_SERVER}")

    async def handleStreamFeatures(self, node) -> Any:
        nodeEntity = StreamFeaturesProtocolEntity.fromProtocolTreeNode(node)
        await self.toUpper(nodeEntity)

    async def handleSuccess(self, node) -> Any:
        successEvent = YowLayerEvent(self.__class__.EVENT_AUTHED, passive = self.getProp(self.__class__.PROP_PASSIVE))
        await self.broadcastEvent(successEvent)
        nodeEntity = SuccessProtocolEntity.fromProtocolTreeNode(node)
        await self.toUpper(nodeEntity)

    async def handleFailure(self, node) -> Any:                
         
        nodeEntity = FailureProtocolEntity.fromProtocolTreeNode(node)
        await self.toUpper(nodeEntity)
        await self.broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT, reason = "Authentication Failure"))

    async def handleStreamError(self, node) -> Any:
        nodeEntity = StreamErrorProtocolEntity.fromProtocolTreeNode(node)

        code = node.getAttributeValue("code")
        if code=="515":
            await self.toUpper(nodeEntity)
            return

        
        errorType = nodeEntity.getErrorType()

        if not errorType and nodeEntity.code is None:
            raise NotImplementedError("Unhandled stream:error node:\n%s" % node)
                

        await self.toUpper(nodeEntity)
