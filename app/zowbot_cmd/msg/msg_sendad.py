"""msg.sendad command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import base64
import logging
import threading
import time
import uuid

from app.zowbot_cmd.base_send import BotSendCommand
from core.common.tools import Jid
from core.layers.protocol_chatstate.protocolentities.chatstate import ChatstateProtocolEntity
from core.layers.protocol_chatstate.protocolentities.chatstate_outgoing import OutgoingChatstateProtocolEntity
from core.layers.protocol_messages.protocolentities.attributes.attributes_context_info import ContextInfoAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_extendedtext import ExtendedTextAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_external_ad_reply import ExternalAdReplyAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from core.layers.protocol_messages.protocolentities.message_extendedtext import ExtendedTextMessageProtocolEntity

logger = logging.getLogger(__name__)


class Cmd_Msg_Sendad(BotSendCommand):

    COMMAND = "msg.sendad"
    DESCRIPTION = "Send ad message"


    async def execute(self, params, options):

        to, *other = params
        bot = self.bot
        
        if "," in to:
            if "broadcast" in options:
                bcid, phash = bot.botLayer.db._store.addBroadcast(jids=params[0], senderJid=bot.botId)
                options["bcid"] = bcid
                options["phash"] = phash        
                
        if "waitMsgId" not in options:
            await self.assureContactsAndSend(params, options, send_func=self.sendAdDirect, redo_func=self.execute)            
            return "JUSTWAIT"
        else:
            ctxId = str(uuid.uuid4())            
            bot.botLayer.ctxMap[ctxId] = {"event": threading.Event()}
            options["ctxId"] = ctxId                        
            await self.assureContactsAndSend(params, options, send_func=self.sendAdDirect, redo_func=self.execute)

    

    async def sendAdDirect(self,params,options):        
        to,text,*others = params
        title = options["title"] if  "title" in options else None
        url = options["url"] if "url" in options else None        
        
        thumbnail = base64.b64decode(options["thumbnailb64"]) if "thumbnailb64" in options else None

        '''
        attr = ExtendedTextAttributes(
            text = "content",
            context_info=ContextInfoAttributes(
                #quoted_ad=AdReplyAttributes(
                #    media_type=1,  # 1 for image, 2 for video
                #),
                conversion_delay_seconds=0,                
                forwarding_score=0,
                is_forwarded=False,
                external_ad_reply=ExternalAdReplyAttributes(
                    title="title",
                    #body = "body",
                    media_type=1,  # 1 for image, 2 for video
                    #thumbnail_url="https://www.baidu.com",
                    #media_url="https://mmg.whatsapp.net/v/t62.36144-24/19481078_703138315880441_858710867709895800_n.enc?ccb=11-4&oh=01_Q5Aa2AHn18y5YgGKkETuf_FNMuHVuNeuwDy4nfT_j3LYc9YrEA&oe=689ECC2E&_nc_sid=5e03e0&mms3=true",
                    #thumbnail=thumbnail if "thumbnailb64" in options else None,
                    #source_type = "Facebook",
                    source_url = "https://www.baidu.com",
                    render_larger_thumbnail = False,
                    show_ad_attribution = False,
                    #source_app = "Facebook",
                    #original_image_url = "https://www.baidu.com",
                    #wtwa_ad_format = False
                ),                 
            )
        )
        '''

                             
        attr = ExtendedTextAttributes(
            text = text,
            context_info=ContextInfoAttributes(
                conversion_delay_seconds=0,                
                forwarding_score=0,
                is_forwarded=False,

                #expiration=0,
                #ephemeral_setting_timestamp=0,
                
                external_ad_reply=ExternalAdReplyAttributes(
                    title=title,
                    media_type=1,
                    thumbnail_url=url,     
                    media_url=options["thumbnailurl"] if "thumbnailurl" in options else None,
                    thumbnail=thumbnail if "thumbnailb64" in options else None,                                       
                    source_url=url,
                    contains_auto_reply=False,
                    render_larger_thumbnail=False,
                    show_ad_attribution=False
                )
            ),
            #doNotPlayInline=False
        )

        target = Jid.normalize(to.split(",")[0])
        if target.endswith("@g.us"):
            entity = OutgoingChatstateProtocolEntity(ChatstateProtocolEntity.STATE_TYPING, target,Jid.normalize(self.bot.botId))
        else:
            entity = OutgoingChatstateProtocolEntity(ChatstateProtocolEntity.STATE_TYPING, target)
        await self.bot.botLayer.toLower(entity)
        time.sleep(1)           
                    
        messageEntity = ExtendedTextMessageProtocolEntity(attr, 
            MessageMetaAttributes(id=self.bot.idType,recipient=Jid.normalize(to),timestamp=int(time.time()))
        )              

        self.bot.botLayer.ackQueue.append(messageEntity.getId())


        await self.bot.botLayer.toLower(messageEntity)          
          
        if "waitMsgId" in options:
            self.bot.botLayer.ctxMap[options["ctxId"]]["msgId"] = messageEntity.getId()
            self.bot.botLayer.ctxMap[options["ctxId"]]["event"].set()            
        
        return messageEntity.getId()        #成功发送，会返回消息ID           