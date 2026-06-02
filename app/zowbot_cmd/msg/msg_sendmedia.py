"""msg.sendmedia command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
import traceback
import traceback
import uuid
import threading

from app.zowbot_cmd.base_send import BotSendCommand
from core.common.tools import Jid
from core.layers.protocol_media.protocolentities.iq_requestmediaconn import RequestMediaConnIqProtocolEntity
from core.layers.protocol_media.protocolentities.iq_requestmediaconn_result import ResultRequestMediaConnIqProtocolEntity
from core.layers.protocol_media.protocolentities.message_media_downloadable_audio import AudioDownloadableMediaMessageProtocolEntity
from core.layers.protocol_media.protocolentities.message_media_downloadable_document import DocumentDownloadableMediaMessageProtocolEntity
from core.layers.protocol_media.protocolentities.message_media_downloadable_image import ImageDownloadableMediaMessageProtocolEntity
from core.layers.protocol_media.protocolentities.message_media_downloadable_video import VideoDownloadableMediaMessageProtocolEntity
from core.layers.protocol_messages.protocolentities.attributes.attributes_audio import AudioAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_document import DocumentAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_image import ImageAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_video import VideoAttributes

logger = logging.getLogger(__name__)



class Cmd_Msg_Sendmedia(BotSendCommand):

    COMMAND = "msg.sendmedia"
    DESCRIPTION = "Send media message"


    async def execute(self, params, options):

        bot = self.bot

        if "waitMsgId" not in options:
            await bot.botLayer.assureContactsAndSend(
                params,
                options,
                send_func=self.sendMediaMsgDirect,
                redo_func=self.execute
            )
            return "JUSTWAIT"
        else:
            ctxId = str(uuid.uuid4())
            bot.botLayer.ctxMap[ctxId] = {"event": threading.Event()}
            options["ctxId"] = ctxId
            
            await self.assureContactsAndSend(
                params,
                options,
                send_func=self.sendMediaMsgDirect,
                redo_func=self.execute
            )
            
            # Wait for message ID callback
            ret = bot.botLayer.ctxMap[ctxId]["event"].wait(
                int(options["waitMsgId"])
            )
            if not ret:
                return "TIMEOUT"
            else:
                msgId = bot.botLayer.getContextValue(ctxId, "msgId")
                del bot.botLayer.ctxMap[ctxId]
                return msgId


    async def sendMediaMsgDirect(self,params,options):

        mediaType = params[1]
        if not mediaType in ["image","video","audio","document"]:
            self.logger.info("sendmedia type %s is not supported now" % mediaType)
            return 

        try:
            entity = RequestMediaConnIqProtocolEntity()
            entity_result = await self.send_iq_expect(entity,ResultRequestMediaConnIqProtocolEntity)                                            
            to, mediaType, filePath,*other = params    
            caption = options["caption"] if "caption" in options else None
            fileName = options["fileName"] if "fileName" in options else None
            
            if mediaType=="image":
                if filePath.startswith("http://") or filePath.startswith("https://"):
                    attr_media = ImageAttributes.from_url(filePath,mediaType,entity_result)
                else:
                    attr_media = ImageAttributes.from_filepath(filePath,mediaType,entity_result)
                attr_media.caption = caption
                
                entity = ImageDownloadableMediaMessageProtocolEntity(
                    image_attrs=attr_media,
                    message_meta_attrs=MessageMetaAttributes(id=self.bot.idType,recipient=Jid.normalize(to))
                )            

            if mediaType=="video":            
                if filePath.startswith("http://") or filePath.startswith("https://"):
                    attr_media = VideoAttributes.from_url(filePath,mediaType,entity_result)
                else:
                    attr_media = VideoAttributes.from_filepath(filePath,mediaType,entity_result)
                attr_media.caption = caption            
                entity = VideoDownloadableMediaMessageProtocolEntity(
                    video_attrs=attr_media,
                    message_meta_attrs=MessageMetaAttributes(id=self.bot.idType,recipient= Jid.normalize(to))
                )                         

            if mediaType=="audio":      
                if filePath.startswith("http://") or filePath.startswith("https://"):
                    attr_media = AudioAttributes.from_url(filePath,mediaType,entity_result)          
                else:      
                    attr_media = AudioAttributes.from_filepath(filePath,mediaType,entity_result)          
                entity = AudioDownloadableMediaMessageProtocolEntity(
                    audio_attrs=attr_media,
                    message_meta_attrs=MessageMetaAttributes(id=self.bot.idType,recipient= Jid.normalize(to))
                )                         
                
            if mediaType=="document":        
                if filePath.startswith("http://") or filePath.startswith("https://"):
                    attr_media = DocumentAttributes.from_url(filePath,fileName,mediaType,entity_result)  
                else:
                    attr_media = DocumentAttributes.from_filepath(filePath,fileName,mediaType,entity_result)          
                entity = DocumentDownloadableMediaMessageProtocolEntity(
                    document_attrs=attr_media,
                    message_meta_attrs=MessageMetaAttributes(id=self.bot.idType,recipient= Jid.normalize(to))
                )                                    

            self.logger.info("Send Media %s Msg (ID=%s)" % (mediaType,entity.getId()))                

            self.bot.botLayer.ackQueue.append(entity.getId())

            self.bot.botLayer.toLower(entity) 


            if "waitMsgId" in options:
                self.bot.botLayer.ctxMap[options["ctxId"]]["msgId"] = entity.getId()
                self.bot.botLayer.ctxMap[options["ctxId"]]["event"].set()            

            return entity.getId()        #成功发送，会返回消息ID                
        except:
            print(traceback.format_exc())
            logger.error("send media msg with exception")
            return None

       