from ...layers import YowLayer, YowLayerEvent
from typing import Optional, Any, List, Dict, Union
from ...layers.protocol_iq.protocolentities import IqProtocolEntity
from ...layers.auth import YowAuthenticationProtocolLayer
from ...layers.protocol_media.protocolentities.iq_requestupload import RequestUploadIqProtocolEntity
from ...layers.protocol_media.mediauploader import MediaUploader
from ...layers.network.layer import YowNetworkLayer
from ...layers.auth.protocolentities import StreamErrorProtocolEntity
from ...layers import EventCallback
import inspect
import asyncio
import logging
logger = logging.getLogger(__name__)
import traceback


class ProtocolEntityCallback:
    def __init__(self, entityType) -> None:
        self.entityType = entityType

    def __call__(self, fn):
        fn.entity_callback = self.entityType
        return fn


class YowInterfaceLayer(YowLayer):

    PROP_RECONNECT_ON_STREAM_ERR = "org.openwhatsapp.zowsup.prop.interface.reconnect_on_stream_error"

    def __init__(self) -> None:
        super().__init__()
        self.reconnect = False
        self.entity_callbacks = {}
        self.iqRegistry = {}
        # self.receiptsRegistry = {}
        members = inspect.getmembers(self, predicate=inspect.ismethod)
        for m in members:
            if hasattr(m[1], "entity_callback"):
                fname = m[0]
                fn = m[1]
                self.entity_callbacks[fn.entity_callback] = getattr(self, fname)

    async def _sendIq(self, iqEntity, onSuccess=None, onError=None) -> Any:
        assert iqEntity.getTag() == "iq", "Expected *IqProtocolEntity in _sendIq, got %s" % iqEntity.getTag()
        self.iqRegistry[iqEntity.getId()] = (iqEntity, onSuccess, onError)
        await self.toLower(iqEntity)

    async def processIqRegistry(self, entity) -> Any:
        """
        :type entity: IqProtocolEntity
        """
        if entity.getTag() == "iq":
            iq_id = entity.getId()
            if iq_id in self.iqRegistry:
                originalIq, successClbk, errorClbk = self.iqRegistry[iq_id]
                del self.iqRegistry[iq_id]

                if entity.getType() == IqProtocolEntity.TYPE_RESULT and successClbk:
                    result = successClbk(entity, originalIq)
                    if inspect.isawaitable(result):
                        await result
                elif entity.getType() == IqProtocolEntity.TYPE_ERROR and errorClbk:
                    result = errorClbk(entity, originalIq)
                    if inspect.isawaitable(result):
                        await result
                return True

        return False

    def getOwnJid(self, full=True) -> Any:
        return self.getLayerInterface(YowAuthenticationProtocolLayer).getUsername(full)

    async def connect(self) -> Any:
        await self.getLayerInterface(YowNetworkLayer).connect()

    async def disconnect(self) -> Any:
        disconnectEvent = YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT)
        await self.broadcastEvent(disconnectEvent)

    async def send(self, data) -> Any:
        await self.toLower(data)

    async def receive(self, entity) -> Any:
        if not await self.processIqRegistry(entity):
            entityType = entity.getTag()
            if entityType in self.entity_callbacks:
                try:
                    result = self.entity_callbacks[entityType](entity)
                    if inspect.isawaitable(result):
                        await result
                except (SystemExit,KeyboardInterrupt):
                    raise
                except:
                    traceback.print_exc()
                    logger.info("EXCEPTION IN DATA PROCESS")
            else:
                await self.toUpper(entity)

    @ProtocolEntityCallback("stream:error")
    async def onStreamError(self, streamErrorEntity) -> Any:
        logger.error(streamErrorEntity)
        if self.getProp(self.__class__.PROP_RECONNECT_ON_STREAM_ERR, True):
            if streamErrorEntity.getErrorType() == StreamErrorProtocolEntity.TYPE_CONFLICT:
                logger.warn("Not reconnecting because you signed in in another location")
            else:
                logger.info("Initiating reconnect")
                self.reconnect = True
        else:
            logger.warn("Not reconnecting because property %s is not set" %
                        self.__class__.PROP_RECONNECT_ON_STREAM_ERR)
        await self.toUpper(streamErrorEntity)
        await self.disconnect()

    @EventCallback(YowNetworkLayer.EVENT_STATE_CONNECTED)
    def onConnected(self, yowLayerEvent) -> Any:
        self.reconnect = False

    @EventCallback(YowNetworkLayer.EVENT_STATE_DISCONNECTED)
    def onDisconnected(self, yowLayerEvent) -> Any:
        if self.reconnect:
            self.reconnect = False
            # connect() is async but event callbacks may not await
            # the isawaitable bridge in onEvent will handle this
            asyncio.ensure_future(self.connect())

    def _sendMediaMessage(self, builder, success, error=None, progress=None) -> Any:
        # axolotlIface = self.getLayerInterface(YowAxolotlLayer)
        # if axolotlIface:
        #     axolotlIface.encryptMedia(builder)

        iq = RequestUploadIqProtocolEntity(
            builder.mediaType, filePath=builder.getFilepath(), encrypted=builder.isEncrypted())

        def successFn(resultEntity, requestUploadEntity): return self.__onRequestUploadSuccess(
            resultEntity, requestUploadEntity, builder, success, error, progress)

        def errorFn(errorEntity, requestUploadEntity): return self.__onRequestUploadError(
            errorEntity, requestUploadEntity, error)
        self._sendIq(iq, successFn, errorFn)

    def __onRequestUploadSuccess(self, resultRequestUploadIqProtocolEntity, requestUploadEntity, builder, success, error=None, progress=None) -> Any:
        if(resultRequestUploadIqProtocolEntity.isDuplicate()):
            return success(builder.build(resultRequestUploadIqProtocolEntity.getUrl(), resultRequestUploadIqProtocolEntity.getIp()))
        else:
            def successFn(path, jid, url): return self.__onMediaUploadSuccess(
                builder, url, resultRequestUploadIqProtocolEntity.getIp(), success)

            def errorFn(path, jid, errorText): return self.__onMediaUploadError(
                builder, errorText, error)

            mediaUploader = MediaUploader(builder.jid, self.getOwnJid(), builder.getFilepath(),
                                          resultRequestUploadIqProtocolEntity.getUrl(),
                                          resultRequestUploadIqProtocolEntity.getResumeOffset(),
                                          successFn, errorFn, progress, asynchronous=True)
            mediaUploader.start()

    def __onRequestUploadError(self, errorEntity, requestUploadEntity, builder, error=None) -> Any:
        if error:
            return error(errorEntity.code, errorEntity.text, errorEntity.backoff)

    def __onMediaUploadSuccess(self, builder, url, ip, successClbk) -> Any:
        messageNode = builder.build(url, ip)
        return successClbk(messageNode)

    def __onMediaUploadError(self, builder, errorText, errorClbk=None) -> Any:
        if errorClbk:
            return errorClbk(0, errorText, 0)

    def __str__(self):
        return "Interface Layer"
