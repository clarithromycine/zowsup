from ...layers import YowLayer, YowLayerEvent, EventCallback
from typing import Optional, Any, List, Dict, Union
from ...layers.network.layer_interface import YowNetworkLayerInterface
from ...layers.network.dispatcher.dispatcher import ConnectionCallbacks
from ...layers.network.dispatcher.dispatcher import YowConnectionDispatcher
from ...layers.network.dispatcher.dispatcher_asyncio import AsyncioConnectionDispatcher
import asyncio
import logging

logger = logging.getLogger(__name__)

class YowNetworkLayer(YowLayer, ConnectionCallbacks):
    """This layer wraps a connection dispatcher that provides connection and a communication channel
    to remote endpoints. Unless explicitly configured, applications should not make assumption about
    the dispatcher being used as the default dispatcher could be changed across versions"""
    EVENT_STATE_CONNECT         = "org.openwhatsapp.zowsup.event.network.connect"
    EVENT_STATE_DISCONNECT      = "org.openwhatsapp.zowsup.event.network.disconnect"
    EVENT_STATE_CONNECTED       = "org.openwhatsapp.zowsup.event.network.connected"
    EVENT_STATE_DISCONNECTED    = "org.openwhatsapp.zowsup.event.network.disconnected"

    PROP_ENDPOINT               = "org.openwhatsapp.zowsup.prop.endpoint"
    PROP_NET_READSIZE           = "org.openwhatsapp.zowsup.prop.net.readSize"
    PROP_DISPATCHER             = "org.openwhatsapp.zowsup.prop.net.dispatcher"

    STATE_DISCONNECTED          = 0
    STATE_CONNECTING            = 1
    STATE_CONNECTED             = 2
    STATE_DISCONNECTING         = 3

    DISPATCHER_ASYNCIO = 2
    DISPATCHER_DEFAULT = DISPATCHER_ASYNCIO

    def __init__(self) -> None:
        self.state = self.__class__.STATE_DISCONNECTED
        YowLayer.__init__(self)
        ConnectionCallbacks.__init__(self)
        self.interface = YowNetworkLayerInterface(self)
        self.connected = False
        self._dispatcher = None  # type: YowConnectionDispatcher
        self._disconnect_reason = None

    def __create_dispatcher(self, dispatcher_type) -> Any:
        logger.debug("Created asyncio dispatcher")
        return AsyncioConnectionDispatcher(self)

    async def onConnected(self) -> Any:
        logger.debug("Connected")
        self.state = self.__class__.STATE_CONNECTED
        self.connected = True
        await self.emitEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECTED))

    async def onDisconnected(self) -> Any:
        if self.state != self.__class__.STATE_DISCONNECTED:
            self.state = self.__class__.STATE_DISCONNECTED
            self.connected = False
            logger.debug("Disconnected")
            await self.emitEvent(
                YowLayerEvent(
                    self.__class__.EVENT_STATE_DISCONNECTED, reason=self._disconnect_reason or "", detached=True
                )
            )

    def onConnecting(self) -> Any:
        pass

    async def onConnectionError(self, error) -> Any:        
        await self.onDisconnected()

    @EventCallback(EVENT_STATE_CONNECT)
    def onConnectLayerEvent(self, ev) -> Any:        
        if not self.connected:
            self.createConnection()
        else:
            logger.warning("Received connect event while already connected")
        return True

    @EventCallback(EVENT_STATE_DISCONNECT)
    def onDisconnectLayerEvent(self, ev) -> Any:
        self.destroyConnection(ev.getArg("reason"))
        return True

    def createConnection(self) -> Any:        
        self._disconnect_reason = None
        self._dispatcher = self.__create_dispatcher(self.getProp(self.PROP_DISPATCHER, self.DISPATCHER_DEFAULT))
        self.state = self.__class__.STATE_CONNECTING
        endpoint = self.getProp(self.__class__.PROP_ENDPOINT)        
        logger.info("Connecting to %s:%s" % endpoint)                    
        self._dispatcher.connect(endpoint)                                  


    def destroyConnection(self, reason=None) -> Any:        
        self._disconnect_reason = reason
        self.state = self.__class__.STATE_DISCONNECTING
        asyncio.ensure_future(self._async_destroy_connection())

    async def _async_destroy_connection(self) -> Any:
        self._dispatcher.disconnect()

    def getStatus(self) -> Any:
        return self.connected

    async def send(self, data) -> Any:
        if self.connected:
            self._dispatcher.sendData(data)

    async def onRecvData(self, data) -> Any:
        await self.receive(data)

    async def receive(self, data) -> Any:
        await self.toUpper(data)

    def __str__(self):
        return "Network Layer"
