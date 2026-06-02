from ..layers import YowParallelLayer
import asyncio, logging, random
from typing import Any, Callable, Optional
from ..layers import YowLayer, YowLayerEvent
from ..layers.noise.layer import YowNoiseLayer
from ..layers.noise.layer_noise_segments import YowNoiseSegmentsLayer
from ..layers.auth                        import YowAuthenticationProtocolLayer
from ..layers.coder                       import YowCoderLayer
from ..layers.logger                      import YowLoggerLayer
from ..layers.network                     import YowNetworkLayer
from ..layers.protocol_messages           import YowMessagesProtocolLayer
from ..layers.protocol_media              import YowMediaProtocolLayer
from ..layers.protocol_acks               import YowAckProtocolLayer
from ..layers.protocol_receipts           import YowReceiptProtocolLayer
from ..layers.protocol_groups             import YowGroupsProtocolLayer
from ..layers.protocol_presence           import YowPresenceProtocolLayer
from ..layers.protocol_ib                 import YowIbProtocolLayer
from ..layers.protocol_notifications      import YowNotificationsProtocolLayer
from ..layers.protocol_iq                 import YowIqProtocolLayer
from ..layers.protocol_contacts           import YowContactsIqProtocolLayer
from ..layers.protocol_devices            import YowDevicesIqProtocolLayer
from ..layers.protocol_chatstate          import YowChatstateProtocolLayer
from ..layers.protocol_privacy            import YowPrivacyProtocolLayer
from ..layers.protocol_profiles           import YowProfilesProtocolLayer
from ..layers.protocol_calls import YowCallsProtocolLayer
from ..common.constants import YowConstants
from ..layers.axolotl import AxolotlSendLayer, AxolotlControlLayer, AxolotlReceivelayer
from ..profile.profile import YowProfile
import inspect

logger = logging.getLogger(__name__)

YOWSUP_PROTOCOL_LAYERS_BASIC = (
    YowAuthenticationProtocolLayer, YowMessagesProtocolLayer,
    YowReceiptProtocolLayer, YowAckProtocolLayer, YowPresenceProtocolLayer,
    YowIbProtocolLayer, YowIqProtocolLayer, YowNotificationsProtocolLayer,
    YowContactsIqProtocolLayer, YowDevicesIqProtocolLayer,YowChatstateProtocolLayer, YowCallsProtocolLayer

)

class YowStackBuilder:
    def __init__(self) -> None:
        self.layers: tuple = ()
        self._props: dict = {}

    def setProp(self, key: str, value: Any) -> 'YowStackBuilder':
        self._props[key] = value
        return self

    def pushDefaultLayers(self) -> 'YowStackBuilder':
        defaultLayers = YowStackBuilder.getDefaultLayers()
        self.layers += defaultLayers       
        return self

    def push(self, yowLayer: Any) -> 'YowStackBuilder':
        self.layers += (yowLayer,)
        return self

    def pop(self) -> 'YowStackBuilder':
        self.layers = self.layers[:-1]
        return self

    def build(self) -> 'YowStack':
        return YowStack(self.layers, reversed = False, props = self._props)

    @staticmethod
    def getDefaultLayers(groups: bool = True, media: bool = True, privacy: bool = True, profiles: bool = True) -> tuple:
        coreLayers = YowStackBuilder.getCoreLayers()
        protocolLayers = YowStackBuilder.getProtocolLayers(groups = groups, media=media, privacy=privacy, profiles=profiles)

        allLayers = coreLayers
        allLayers += (AxolotlControlLayer,)
        allLayers += (YowParallelLayer((AxolotlSendLayer, AxolotlReceivelayer)),)

        allLayers += (YowParallelLayer(protocolLayers),)
                
        
        return allLayers

    @staticmethod
    def getDefaultStack(layer: Optional[YowLayer] = None, axolotl: bool = False, groups: bool = True, media: bool = True, privacy: bool = True, profiles: bool = True) -> 'YowStack':
        """
        :param layer: An optional layer to put on top of default stack
        :param axolotl: E2E encryption enabled/ disabled
        :return: YowStack
        """

        allLayers = YowStackBuilder.getDefaultLayers(axolotl, groups = groups, media=media,privacy=privacy, profiles=profiles)
        if layer:
            allLayers = allLayers + (layer,)


        return YowStack(allLayers, reversed = False)

    @staticmethod
    def getCoreLayers() -> tuple:
        return (
            YowLoggerLayer,
            YowCoderLayer,
            YowNoiseLayer,
            YowNoiseSegmentsLayer,
            YowNetworkLayer
        )[::-1]

    @staticmethod
    def getProtocolLayers(groups: bool = True, media: bool = True, privacy: bool = True, profiles: bool = True) -> tuple:
        layers = YOWSUP_PROTOCOL_LAYERS_BASIC
        if groups:
            layers += (YowGroupsProtocolLayer,)
        if media:
            layers += (YowMediaProtocolLayer, )
        if profiles:
            layers += (YowProfilesProtocolLayer, )
        if privacy:
            layers += (YowPrivacyProtocolLayer, )            
        return layers

class YowStack:
    
    def __init__(self, stackClassesArr: Optional[tuple] = None, reversed: bool = True, props: Optional[dict] = None) -> None:
        stackClassesArr = stackClassesArr or ()
        self.__stack = stackClassesArr[::-1] if reversed else stackClassesArr
        self.__stackInstances: list[YowLayer] = []
        self._props: dict[str, Any] = props or {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None        
        self.setProp(YowNetworkLayer.PROP_ENDPOINT, YowConstants.ENDPOINTS[random.randint(0,len(YowConstants.ENDPOINTS)-1)])
        self._construct()


    def getLayerInterface(self, YowLayerClass: type) -> Optional['YowLayerInterface']:
        for inst in self.__stackInstances:
            if inst.__class__ == YowLayerClass:
                return inst.getLayerInterface()
            elif inst.__class__ == YowParallelLayer:
                res = inst.getLayerInterface(YowLayerClass)
                if res:
                    return res
        return None
                
    async def send(self, data: Any) -> None:
        await self.__stackInstances[-1].send(data)

    async def receive(self, data: Any) -> None:
        await self.__stackInstances[0].receive(data)

    def setCredentials(self, credentials: tuple) -> None:
        logger.warning("setCredentials is deprecated and any passed-in keypair is ignored, "
                       "use setProfile(YowProfile) instead")
        profile_name, keypair = credentials              
        self.setProfile(YowProfile(profile_name))

    def setProfile(self, profile: Any) -> None:
        logger.debug("setProfile(%s)" % profile)
        if self.getProfile() is None:                  
            self.setProp("profile", profile if isinstance(profile, YowProfile) else YowProfile(profile))
        
    def getProfile(self) -> Optional[YowProfile]:
        return self.getProp("profile")
    
    def addLayer(self, layerClass: type) -> None:
        self.__stack.push(layerClass)

    def addPostConstructLayer(self, layer: YowLayer) -> None:
        self.__stackInstances[-1].setLayers(layer, self.__stackInstances[-2])
        layer.setLayers(None, self.__stackInstances[-1])
        self.__stackInstances.append(layer)

    def setProp(self, key: str, value: Any) -> None:
        self._props[key] = value

    def getProp(self, key: str, default: Any = None) -> Any:
        return self._props[key] if key in self._props else default

    async def emitEvent(self, yowLayerEvent: YowLayerEvent) -> None:
        result = self.__stackInstances[0].onEvent(yowLayerEvent)
        if inspect.isawaitable(result):
            stopped = await result
        else:
            stopped = result
        if not stopped:
            await self.__stackInstances[0].emitEvent(yowLayerEvent)

    async def broadcastEvent(self, yowLayerEvent: YowLayerEvent) -> None:
        result = self.__stackInstances[-1].onEvent(yowLayerEvent)
        if inspect.isawaitable(result):
            stopped = await result
        else:
            stopped = result
        if not stopped:
            await self.__stackInstances[-1].broadcastEvent(yowLayerEvent)
            
    def getLoop(self) -> Optional[asyncio.AbstractEventLoop]:
        """Return the running asyncio event loop (available after loop() is called)."""
        return self._loop

    async def loop(self) -> None:
        """Yield control to the asyncio event loop until THREADQUIT or QUITTED is set."""
        self._loop = asyncio.get_running_loop()        
        while True:
            if self.getProp("THREADQUIT") or self.getProp("QUITTED"):
                break
            await asyncio.sleep(0.1)
            
            
            
            
    def _construct(self) -> None:
        logger.debug("Initializing stack")
        for s in self.__stack:
            if type(s) is tuple:
                logger.warn("Implicit declaration of parallel layers in a tuple is deprecated, pass a YowParallelLayer instead")
                inst = YowParallelLayer(s)
            else:
                if inspect.isclass(s):
                    if issubclass(s, YowLayer):
                        inst = s()
                    else:
                        raise ValueError("Stack must contain only subclasses of YowLayer")
                elif issubclass(s.__class__, YowLayer):
                        inst = s
                else:
                    raise ValueError("Stack must contain only subclasses of YowLayer")
                #inst = s()
            logger.debug("Constructed %s" % inst)
            inst.setStack(self)
            self.__stackInstances.append(inst)

        for i in range(0, len(self.__stackInstances)):
            upperLayer = self.__stackInstances[i + 1] if (i + 1) < len(self.__stackInstances) else None
            lowerLayer = self.__stackInstances[i - 1] if i > 0 else None
            self.__stackInstances[i].setLayers(upperLayer, lowerLayer)

    def getLayer(self, layerIndex: int) -> YowLayer:
        return self.__stackInstances[layerIndex]
