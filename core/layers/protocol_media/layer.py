from ...layers import YowProtocolLayer
from typing import Optional, Any, List, Dict, Union
from .protocolentities import ImageDownloadableMediaMessageProtocolEntity
from .protocolentities import AudioDownloadableMediaMessageProtocolEntity
from .protocolentities import VideoDownloadableMediaMessageProtocolEntity
from .protocolentities import DocumentDownloadableMediaMessageProtocolEntity
from .protocolentities import StickerDownloadableMediaMessageProtocolEntity
from .protocolentities import LocationMediaMessageProtocolEntity
from .protocolentities import ContactMediaMessageProtocolEntity
from .protocolentities import ResultRequestUploadIqProtocolEntity
from .protocolentities import MediaMessageProtocolEntity
from .protocolentities import ExtendedTextMediaMessageProtocolEntity
from .protocolentities import ButtonsResponseMediaMessageProtocolEntity
from .protocolentities import ListResponseMediaMessageProtocolEntity
from .protocolentities import ProductMediaMessageProtocolEntity
from ...layers.protocol_iq.protocolentities import IqProtocolEntity, ErrorIqProtocolEntity
import logging
import traceback

logger = logging.getLogger(__name__)


class YowMediaProtocolLayer(YowProtocolLayer):
    def __init__(self) -> None:
        handleMap = {
            "message": (self.recvMessageStanza, self.sendMessageEntity),
            "iq": (self.recvIq, self.sendIq)
        }
        super().__init__(handleMap)

    def __str__(self):
        return "Media Layer"

    async def sendMessageEntity(self, entity) -> Any:
        if entity.getType() == "media":                    
            await self.entityToLower(entity)

    async def recvMessageStanza(self, node) -> Any:    


                                
        if node.getAttributeValue("type") == "medianotify":
            await self.toLower(MediaMessageProtocolEntity.fromProtocolTreeNode(node).ack(True).toProtocolTreeNode())
            
        if node.getAttributeValue("type") == "media":                                          
            mediaNode = node.getChild("proto")                         
            if mediaNode is None:
                return
                        
            try:                
                if mediaNode.getAttributeValue("mediatype") == "image":
                    entity = ImageDownloadableMediaMessageProtocolEntity.fromProtocolTreeNode(node)     
                    await self.toUpper(entity)
                elif mediaNode.getAttributeValue("mediatype") == "sticker":
                    entity = StickerDownloadableMediaMessageProtocolEntity.fromProtocolTreeNode(node)
                    await self.toUpper(entity)
                elif mediaNode.getAttributeValue("mediatype") in ("audio", "ptt"):
                    entity = AudioDownloadableMediaMessageProtocolEntity.fromProtocolTreeNode(node)
                    await self.toUpper(entity)
                elif mediaNode.getAttributeValue("mediatype") in ("video", "gif"):
                    entity = VideoDownloadableMediaMessageProtocolEntity.fromProtocolTreeNode(node)
                    await self.toUpper(entity)
                elif mediaNode.getAttributeValue("mediatype") == "location":
                    entity = LocationMediaMessageProtocolEntity.fromProtocolTreeNode(node)
                    await self.toUpper(entity)
                elif mediaNode.getAttributeValue("mediatype") == "vcard":
                    entity = ContactMediaMessageProtocolEntity.fromProtocolTreeNode(node)
                    await self.toUpper(entity)
                elif mediaNode.getAttributeValue("mediatype") == "document":                    
                    entity = DocumentDownloadableMediaMessageProtocolEntity.fromProtocolTreeNode(node)
                    await self.toUpper(entity)
                elif mediaNode.getAttributeValue("mediatype") == "url":                
                    entity = ExtendedTextMediaMessageProtocolEntity.fromProtocolTreeNode(node)                                  
                    await self.toUpper(entity)
                elif mediaNode.getAttributeValue("mediatype") == "buttons_response":
                    entity = ButtonsResponseMediaMessageProtocolEntity.fromProtocolTreeNode(node)                
                    await self.toUpper(entity)
                elif mediaNode.getAttributeValue("mediatype") == "list_response":
                    entity = ListResponseMediaMessageProtocolEntity.fromProtocolTreeNode(node)                
                    await self.toUpper(entity)                
                elif mediaNode.getAttributeValue("mediatype") == "product":
                    entity = ProductMediaMessageProtocolEntity.fromProtocolTreeNode(node)                
                    await self.toUpper(entity)                     

                elif mediaNode.getAttributeValue("mediatype") == "1p_sticker":
                    entity = StickerDownloadableMediaMessageProtocolEntity.fromProtocolTreeNode(node)
                    await self.toUpper(entity)
                elif mediaNode.getAttributeValue("mediatype") == "avatar_sticker":
                    entity = StickerDownloadableMediaMessageProtocolEntity.fromProtocolTreeNode(node)
                    await self.toUpper(entity)
                else:
                    logger.warn("Unsupported mediatype: %s, will send receipts" % mediaNode.getAttributeValue("mediatype"))
                    await self.toLower(MediaMessageProtocolEntity.fromProtocolTreeNode(node).ack(True).toProtocolTreeNode())
            
            except Exception:
                logger.error(traceback.format_exc())
                logger.warn("mediatype: %s, process with exception " % mediaNode.getAttributeValue("mediatype"))
                await self.toLower(MediaMessageProtocolEntity.fromProtocolTreeNode(node).ack(True).toProtocolTreeNode())

    

    async def sendIq(self, entity) -> Any:
        """
        :type entity: IqProtocolEntity
        """
        if entity.getType() == IqProtocolEntity.TYPE_SET and entity.getXmlns() == "w:m":
            #media conn!
            await self._sendIq(entity, self.onRequestMediaConnSuccess, self.onRequestMediaConnError)

    def recvIq(self, node) -> Any:
        pass        
        """
        :type node: ProtocolTreeNode
        """

    async def onRequestMediaConnSuccess(self, resultNode, requestUploadEntity) -> Any:
        await self.toUpper(ResultRequestUploadIqProtocolEntity.fromProtocolTreeNode(resultNode))

    async def onRequestMediaConnError(self, errorNode, requestUploadEntity) -> Any:
        await self.toUpper(ErrorIqProtocolEntity.fromProtocolTreeNode(errorNode))
