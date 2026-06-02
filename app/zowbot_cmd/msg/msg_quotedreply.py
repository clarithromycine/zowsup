"""msg.quotedreply command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
import uuid
import threading
import time
from core.common.tools import Jid
from app.zowbot_cmd.base import BotCommand
from app.zowbot_cmd.base_send import BotSendCommand
from core.layers.protocol_messages.protocolentities.attributes.attributes_context_info import ContextInfoAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_extendedtext import ExtendedTextAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_message import MessageAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from core.layers.protocol_messages.protocolentities.message_extendedtext import ExtendedTextMessageProtocolEntity
from proto import zowsup_pb2
logger = logging.getLogger(__name__)


class Cmd_Msg_Quotedreply(BotSendCommand):

    COMMAND = "msg.quotedreply"
    DESCRIPTION = "Send quoted reply message"


    async def execute(self, params, options):

        bot = self.bot
        if "waitMsgId" not in options:
            await self.assureContactsAndSend(
                params,
                options,
                send_func=self.sendQuotedReplyDirect,
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
                send_func=bot.botLayer.sendQuotedReplyDirect,
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


    
    async def sendQuotedReplyDirect(self,params,options):

        to,text,*other = params

        ctx = ContextInfoAttributes()

        '''
        如果设置了stanzaid   则对方会引用对应的消息内容
        如果stanzaid==None, 则对方会读取quotedtext作为引用内容
        '''

        ctx.stanza_id = options["stanzaid"] if "stanzaid" in options else None
        ctx.participant = Jid.normalize(to)
        ctx.quoted_message = MessageAttributes(extended_text=ExtendedTextAttributes(
            text = options["quotedtext"] if "quotedtext" in options else "***",
            preview_type=0,            
            invite_link_group_type_v2=0
        ))

        attr = ExtendedTextAttributes(
            text = text,
            preview_type=0,
            context_info= ctx,
            invite_link_group_type_v2=0
        )          

        messageEntity = ExtendedTextMessageProtocolEntity(attr, 
            MessageMetaAttributes(id=self.bot.idType,recipient=Jid.normalize(to),timestamp=int(time.time()))
        )              

        self.bot.botLayer.ackQueue.append(messageEntity.getId())
        await self.bot.botLayer.toLower(messageEntity)       

        if "waitMsgId" in options:
            self.bot.botLayer.ctxMap[options["ctxId"]]["msgId"] = messageEntity.getId()
            self.bot.botLayer.ctxMap[options["ctxId"]]["event"].set()            
        
        return messageEntity.getId()        #成功发送，会返回消息ID