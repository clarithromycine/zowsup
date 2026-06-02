import unittest
import inspect
import asyncio
from typing import Any, Callable, Optional

class YowLayerEvent:
    def __init__(self, name: str, **kwargs: Any) -> None:
        self.name = name
        self.detached = False
        if "detached" in kwargs:
            del kwargs["detached"]
            self.detached = True
        self.args = kwargs

    def isDetached(self) -> bool:
        return self.detached

    def getName(self) -> str:
        return self.name

    def getArg(self, name: str) -> Any:
        return self.args[name] if name in self.args else None
    
class EventCallback:
    def __init__(self, eventName: str) -> None:
        self.eventName: str = eventName

    def __call__(self, fn: Callable) -> Callable:
        fn.event_callback = self.eventName
        return fn


class YowLayer:
    __upper: Optional['YowLayer'] = None
    __lower: Optional['YowLayer'] = None
    _props: dict[str, Any] = {}

    def __init__(self) -> None:
        self.setLayers(None, None)
        self.interface: Optional['YowLayerInterface'] = None
        self.event_callbacks: dict[str, Callable] = {}
        self.__stack: Optional[Any] = None  # YowStack (circular import)
        members = inspect.getmembers(self, predicate=inspect.ismethod)
        for m in members:
            if hasattr(m[1], "event_callback"):
                fname = m[0]
                fn = m[1]
                self.event_callbacks[fn.event_callback] = getattr(self, fname)

    def getLayerInterface(self, YowLayerClass=None) -> Optional['YowLayerInterface']:
        return self.interface if YowLayerClass is None else self.__stack.getLayerInterface(YowLayerClass)

    def setStack(self, stack) -> None:
        self.__stack = stack

    def getStack(self):
        return self.__stack

    def setLayers(self, upper: Optional['YowLayer'], lower: Optional['YowLayer']) -> None:
        self.__upper = upper
        self.__lower = lower

    async def send(self, data: Any) -> None:
        await self.toLower(data)

    async def receive(self, data: Any) -> None:
        await self.toUpper(data)

    async def toUpper(self, data: Any) -> None:
        if self.__upper:
            result = self.__upper.receive(data)
            if inspect.isawaitable(result):
                await result

    async def toLower(self, data: Any) -> None:
        if self.__lower:
            result = self.__lower.send(data)
            if inspect.isawaitable(result):
                await result

    async def emitEvent(self, yowLayerEvent: YowLayerEvent) -> None:
        if self.__upper:
            result = self.__upper.onEvent(yowLayerEvent)
            if inspect.isawaitable(result):
                stopped = await result
            else:
                stopped = result
            if not stopped:
                if yowLayerEvent.isDetached():
                    yowLayerEvent.detached = False
                    asyncio.ensure_future(self.__upper.emitEvent(yowLayerEvent))
                else:
                    await self.__upper.emitEvent(yowLayerEvent)

    async def broadcastEvent(self, yowLayerEvent: YowLayerEvent) -> None:
        if self.__lower:
            result = self.__lower.onEvent(yowLayerEvent)
            if inspect.isawaitable(result):
                stopped = await result
            else:
                stopped = result
            if not stopped:
                if yowLayerEvent.isDetached():
                    yowLayerEvent.detached = False
                    asyncio.ensure_future(self.__lower.broadcastEvent(yowLayerEvent))
                else:
                    await self.__lower.broadcastEvent(yowLayerEvent)

    '''return true to stop propagating the event'''
    async def onEvent(self, yowLayerEvent: YowLayerEvent) -> bool:
        eventName = yowLayerEvent.getName()
        if eventName in self.event_callbacks:
            result = self.event_callbacks[eventName](yowLayerEvent)
            if inspect.isawaitable(result):
                return await result
            return result
        return False

    def getProp(self, key: str, default: Any = None) -> Any:
        return self.getStack().getProp(key, default)

    def setProp(self, key: str, val: Any) -> None:
        return self.getStack().setProp(key, val)


class YowProtocolLayer(YowLayer):
    def __init__(self, handleMap: Optional[dict] = None) -> None:
        super().__init__()
        self.handleMap: dict = handleMap or {}
        self.iqRegistry: dict = {}

    async def receive(self, node: Any) -> None:
        if not await self.processIqRegistry(node):
            if node.tag in self.handleMap:
                recv, _ = self.handleMap[node.tag]
                if recv:
                    result = recv(node)
                    if inspect.isawaitable(result):
                        await result

    async def send(self, entity: Any) -> None:
        if entity.getTag() in self.handleMap:
            _, send = self.handleMap[entity.getTag()]
            if send:
                result = send(entity)
                if inspect.isawaitable(result):
                    await result

    async def entityToLower(self, entity: Any) -> None:
        await self.toLower(entity.toProtocolTreeNode())

    def isGroupJid(self, jid: str) -> bool:
        return "-" in jid

    def raiseErrorForNode(self, node: Any) -> None:
        raise ValueError("Unimplemented notification type %s " % node)


    async def _sendIq(self, iqEntity: Any, onSuccess: Optional[Callable] = None, onError: Optional[Callable] = None) -> None:
        self.iqRegistry[iqEntity.getId()] = (iqEntity, onSuccess, onError)
        await self.toLower(iqEntity.toProtocolTreeNode())

    async def processIqRegistry(self, protocolTreeNode: Any) -> bool:
        if protocolTreeNode.tag == "iq":
            iq_id = protocolTreeNode["id"]
            if iq_id in self.iqRegistry:
                originalIq, successClbk, errorClbk = self.iqRegistry[iq_id]
                del self.iqRegistry[iq_id]

                if protocolTreeNode["type"] == "result" and successClbk:
                    result = successClbk(protocolTreeNode, originalIq)
                    if inspect.isawaitable(result):
                        await result
                elif protocolTreeNode["type"] == "error" and errorClbk:
                    result = errorClbk(protocolTreeNode, originalIq)
                    if inspect.isawaitable(result):
                        await result
                return True

        return False

class YowParallelLayer(YowLayer):
    def __init__(self, sublayers: Optional[list] = None) -> None:
        super().__init__()
        self.sublayers = sublayers or []
        self.sublayers = tuple([sublayer() for sublayer in sublayers])
        for s in self.sublayers:
            #s.setLayers(self, self)
            s.toLower = self.toLower
            s.toUpper = self.toUpper
            s.broadcastEvent = self.subBroadcastEvent
            s.emitEvent = self.subEmitEvent


    def getLayerInterface(self, YowLayerClass: type) -> Optional['YowLayerInterface']:
        for s in self.sublayers:
            if s.__class__ == YowLayerClass:
                return s.getLayerInterface()
        return None

    def setStack(self, stack: Any) -> None:
        super().setStack(stack)
        for s in self.sublayers:
            s.setStack(self.getStack())


    async def receive(self, data: Any) -> None:
        for s in self.sublayers:
            result = s.receive(data)
            if inspect.isawaitable(result):
                await result

    async def send(self, data: Any) -> None:
        for s in self.sublayers:
            result = s.send(data)
            if inspect.isawaitable(result):
                await result

    async def subBroadcastEvent(self, yowLayerEvent: YowLayerEvent) -> None:
        await self.onEvent(yowLayerEvent)
        await self.broadcastEvent(yowLayerEvent)

    async def subEmitEvent(self, yowLayerEvent: YowLayerEvent) -> None:
        await self.onEvent(yowLayerEvent)
        await self.emitEvent(yowLayerEvent)


    async def onEvent(self, yowLayerEvent: YowLayerEvent) -> bool:
        stopEvent: bool = False
        for s in self.sublayers:
            result = s.onEvent(yowLayerEvent)
            if inspect.isawaitable(result):
                result = await result
            stopEvent = stopEvent or result

        return stopEvent

    def __str__(self) -> str:
        return " - ".join([l.__str__() for l in self.sublayers])

class YowLayerInterface:
    def __init__(self, layer: YowLayer) -> None:
        self._layer: YowLayer = layer


class YowLayerTest(unittest.TestCase):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.upperSink: list = []
        self.lowerSink: list = []
        self.toUpper = self.receiveOverrider
        self.toLower = self.sendOverrider
        self.upperEventSink: list = []
        self.lowerEventSink: list = []
        self.emitEvent = self.emitEventOverrider
        self.broadcastEvent = self.broadcastEventOverrider

    async def receiveOverrider(self, data: Any) -> None:
        self.upperSink.append(data)

    async def sendOverrider(self, data: Any) -> None:
        self.lowerSink.append(data)
        
    async def emitEventOverrider(self, event: YowLayerEvent) -> None:
        self.upperEventSink.append(event)
    
    async def broadcastEventOverrider(self, event: YowLayerEvent) -> None:
        self.lowerEventSink.append(event)
        
    async def assert_emitEvent(self, event: YowLayerEvent) -> None:
        await self.emitEvent(event)
        try:
            self.assertEqual(event, self.upperEventSink.pop())
        except IndexError:
            raise AssertionError("Event '%s' was not emited through this layer" % (event.getName()))
        
    async def assert_broadcastEvent(self, event: YowLayerEvent) -> None:
        await self.broadcastEvent(event)
        try:
            self.assertEqual(event, self.lowerEventSink.pop())
        except IndexError:
            raise AssertionError("Event '%s' was not broadcasted through this layer" % (event.getName()))

class YowProtocolLayerTest(YowLayerTest):
    async def assertSent(self, entity: Any) -> None:
        await self.send(entity)
        try:
            self.assertEqual(entity.toProtocolTreeNode(), self.lowerSink.pop())
        except IndexError:
            raise AssertionError("Entity '%s' was not sent through this layer" % (entity.getTag()))

    async def assertReceived(self, entity: Any) -> None:
        node = entity.toProtocolTreeNode()
        await self.receive(node)
        try:
            self.assertEqual(node, self.upperSink.pop().toProtocolTreeNode())
        except IndexError:
            raise AssertionError("'%s' was not received through this layer" % (entity.getTag()))
