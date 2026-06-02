import asyncio
from typing import Optional, Any, List, Dict, Union
import logging
from ...layers import YowProtocolLayer, YowLayerEvent, EventCallback
from ...common import YowConstants
from ...layers.axolotl.protocolentities.iq_keys_get_result import ResultGetKeysIqProtocolEntity
from ...layers.axolotl.protocolentities.iq_key_count import ResultKeyCountIqProtocolEntity 

from ...layers.protocol_profiles.protocolentities import *
from ...layers.protocol_groups.protocolentities import *
from ...layers.protocol_contacts.protocolentities import *
from ...layers.network import YowNetworkLayer
from ...layers.auth import YowAuthenticationProtocolLayer
from .protocolentities import *

from ...layers.protocol_media.protocolentities  import *
from ...layers.protocol_media.protocolentities.iq_requestmediaconn_result import ResultRequestMediaConnIqProtocolEntity

class YowIqProtocolLayer(YowProtocolLayer):
    
    PROP_PING_INTERVAL               = "org.openwhatsapp.zowsup.prop.pinginterval"
    
    def __init__(self) -> None:
        handleMap = {
            "iq": (self.recvIq, self.sendIq)
        }
        self._ping_task = None
        self._pingQueue = {}
        self.__logger = logging.getLogger(__name__)
        super().__init__(handleMap)

    def __str__(self):
        return "Iq Layer"

    async def onPong(self, protocolTreeNode, pingEntity) -> Any:
        self.gotPong(pingEntity.getId())
        await self.toUpper(ResultIqProtocolEntity.fromProtocolTreeNode(protocolTreeNode))

    async def sendIq(self, entity) -> Any:
        if entity.getXmlns() == "w:p":
            await self._sendIq(entity, self.onPong)
        elif entity.getXmlns() in ("optoutlist","abt","w:auth:key","w:stats","fb:thrift_iq","tos","w:sync:app:state","privacy","urn:xmpp:whatsapp:push", "w", "w:b","w:qr","urn:xmpp:whatsapp:account", "encrypt","w:biz","w:mex","urn:xmpp:whatsapp:dirty","md","w:account_defence") or entity.getXmlns() is None :                
            node =     entity.toProtocolTreeNode()    
            await self.toLower(node)

    async def recvIq(self, node) -> Any:                    
        if node["xmlns"] == "urn:xmpp:ping":
            entity = PongResultIqProtocolEntity(YowConstants.DOMAIN, node["id"])
            await self.toLower(entity.toProtocolTreeNode())

        if node["xmlns"] == "md" :
            if node.getChild("pair-device") is not None:
                #僚机配对，直接回复一个            
                #丢到应用层处理            
                await self.toUpper(MultiDevicePairIqProtocolEntity.fromProtocolTreeNode(node))
                self.onAuthed(None)  #这里主要启动ping线程     
            if node.getChild("pair-success"):
                await self.toUpper(MultiDevicePairSuccessIqProtocolEntity.fromProtocolTreeNode(node))

        if node["type"] == "error":
            await self.toUpper(ErrorIqProtocolEntity.fromProtocolTreeNode(node))
                        

        if node["type"] == "result":            
            if not node.hasChildren():             
                await self.toUpper(ResultIqProtocolEntity.fromProtocolTreeNode(node))
                
            elif node.getChild("verified_name") is not None :
                if node.getChild("verified_name").getData() is not None:                                
                    await self.toUpper(GetBusinessNameResultIqProtocolEntity.fromProtocolTreeNode(node))                                   
                else:
                    await self.toUpper(SetBusinessNameResultIqProtocolEntity.fromProtocolTreeNode(node))

            elif node.getChild("marketing_messages") is not None:
                await self.toUpper(GetBusinessFeatureResultIqProtocolEntity.fromProtocolTreeNode(node))
                                    
            elif node.getChild("media_conn") is not None:
                await self.toUpper(ResultRequestMediaConnIqProtocolEntity.fromProtocolTreeNode(node))

            elif node.getChild("sync") is not None:
                await self.toUpper(ResultAppSyncStateIqResponseProtocolEntity.fromProtocolTreeNode(node))

            elif node.getChild("cat") is not None:                
                await self.toUpper(PushGetCatResultIqProtocolEntity.fromProtocolTreeNode(node))

            elif node.getChild("qrs") is not None:
                await self.toUpper(GetShortLinkResultIqProtocolEntity.fromProtocolTreeNode(node))
            elif node.getChild("qr") is not None:
                qr = node.getChild("qr")
                if qr.getAttributeValue("jid") is not None:
                    await self.toUpper(DecodeShortLinkResultIqProtocolEntity.fromProtocolTreeNode(node))
                else:
                    if qr.getChild("message") is not None:
                        await self.toUpper(SetMsgShortLinkResultIqProtocolEntity.fromProtocolTreeNode(node))
                    else:
                        await self.toUpper(ResetShortLinkResultIqProtocolEntity.fromProtocolTreeNode(node))

            elif node.getChild("list") is not None:
                if self.getProp("CHECKNUM_MODE",False):
                    #这是查号模式，不用建立会话之类的东西浪费资源
                    await self.toUpper(ResultGetKeysIqProtocolEntity.fromProtocolTreeNodeCheckNum(node))
                else:
                    await self.toUpper(ResultGetKeysIqProtocolEntity.fromProtocolTreeNode(node))
                    
            elif node.getChild("usync") is not None:
                pass  #usync 相关的消息在protocol_contacts里面处理  
            elif node.getChild("companion-props") is not None:
                #配对返回僚机的jid，要处理                
                await self.toUpper(MultiDevicePairDeviceResultIqProtocolEntity.fromProtocolTreeNode(node))
            elif node.getChild("groups") is not None or node.getChild("group") is not None or node["from"].endswith("g.us"):
                pass  #group 相关的消息在protocol_groups里面处理
            elif node.getChild("account") is not None:                
                await self.toUpper(AccountInfoResultIqProtocolEntity.fromProtocolTreeNode(node))    
            elif node.getChild("email") is not None:
                await self.toUpper(EmailResultIqProtocolEntity.fromProtocolTreeNode(node))
            elif node.getChild("verify_email") is not None:
                await self.toUpper(VerifyEmailResultIqProtocolEntity.fromProtocolTreeNode(node))  
            elif node.getChild("device_logout") is not None:                
                await self.toUpper(DeviceLogoutResultIqProtocolEntity.fromProtocolTreeNode(node))                 
            elif node.getChild("count") is not None:                
                await self.toUpper(ResultKeyCountIqProtocolEntity.fromProtocolTreeNode(node))      
            elif node.getChild("picture"):
                pic=node.getChild("picture")
                if pic.getAttributeValue("type"):
                    await self.toUpper(ResultGetPictureIqProtocolEntity.fromProtocolTreeNode(node))
                else:                                  
                    await self.toUpper(ResultSetPictureIqProtocolEntity.fromProtocolTreeNode(node))                
            elif node.getChild("result") is not None:
                await self.toUpper(WmexResultIqProtocolEntity.fromProtocolTreeNode(node))           
            else:
                #不知道是啥，打印出来                     
                self.__logger.info(node)
                                
    def gotPong(self, pingId) -> Any:
        if pingId in self._pingQueue:
            del self._pingQueue[pingId]

    def waitPong(self, id) -> Any:
        self._pingQueue[id] = None
        pingQueueSize = len(self._pingQueue)
        self.__logger.debug("ping queue size: %d" % pingQueueSize)
        if pingQueueSize >= 3:
            loop = self.getStack().getLoop()
            asyncio.run_coroutine_threadsafe(
                self.getStack().broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT, reason="Ping Timeout")),
                loop
            )

    @EventCallback(YowAuthenticationProtocolLayer.EVENT_AUTHED)
    def onAuthed(self, event) -> Any:        
        interval = self.getProp(self.__class__.PROP_PING_INTERVAL, 50)
        if not self._ping_task and interval > 0:
            self._pingQueue = {}
            self._ping_task = asyncio.ensure_future(self._ping_loop(interval))
            self.__logger.debug("starting ping task (interval=%d)", interval)
    
    
    def stop_ping(self) -> Any:
        if self._ping_task and not self._ping_task.done():
            self.__logger.debug("stopping ping task")
            self._ping_task.cancel()
            self._ping_task = None
        self._pingQueue = {}
            
    @EventCallback(YowNetworkLayer.EVENT_STATE_DISCONNECT)
    def onDisconnect(self, event) -> Any:                
        self.stop_ping()
    
    @EventCallback(YowNetworkLayer.EVENT_STATE_DISCONNECTED)
    def onDisconnected(self, event) -> Any:                
        self.stop_ping()

    async def _ping_loop(self, interval) -> Any:
        """Async ping loop that sends periodic pings."""
        try:
            while True:
                await asyncio.sleep(interval)
                ping = PingIqProtocolEntity()
                self.waitPong(ping.getId())
                await self.sendIq(ping)
        except asyncio.CancelledError:
            self.__logger.debug("ping task cancelled")
            return
