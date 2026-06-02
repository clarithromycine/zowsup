"""msg.send command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
import uuid
import threading
from app.param_not_enough_exception import ParamsNotEnoughException
from core.common.tools import Jid
from app.zowbot_cmd.base_send import BotSendCommand
from core.layers.protocol_chatstate.protocolentities.chatstate import ChatstateProtocolEntity
from core.layers.protocol_chatstate.protocolentities.chatstate_outgoing import OutgoingChatstateProtocolEntity
from core.layers.protocol_messages.protocolentities.attributes.attributes_business_message_forward_info import BusinessMessageForwardInfoAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_context_info import ContextInfoAttributes
import time,random

from core.layers.protocol_messages.protocolentities.attributes.attributes_disappearing_mode import DisappearingModeAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_extendedtext import ExtendedTextAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from core.layers.protocol_messages.protocolentities.message_extendedtext import ExtendedTextMessageProtocolEntity
from proto import zowsup_pb2

logger = logging.getLogger(__name__)


class Cmd_Msg_Send(BotSendCommand):

    COMMAND = "msg.send"
    DESCRIPTION = "Send a message"

    async def execute(self, params, options):

        if len(params) < 1:
            raise ParamsNotEnoughException()
        
        to = params[0]
        
        # Handle broadcast mode setup
        if "," in to:
            if "broadcast" in options:
                bcid, phash = self.bot.botLayer.db._store.addBroadcast(
                    jids=params[0],
                    senderJid=self.bot.botId
                )
                options["bcid"] = bcid
                options["phash"] = phash
            else:
                logger.error("Multiple targets only allowed in broadcast mode")
        
        # Send with or without message ID tracking
        if "waitMsgId" not in options:
            await self.assureContactsAndSend(
                params,
                options,
                send_func=self.sendMsgDirect,
                redo_func=self.execute
            )
            return "JUSTWAIT"
        else:
            ctxId = str(uuid.uuid4())
            self.bot.botLayer.ctxMap[ctxId] = {"event": threading.Event()}
            options["ctxId"] = ctxId
            
            await self.assureContactsAndSend(
                params,
                options,
                send_func=self.sendMsgDirect,
                redo_func=self.execute
            )
            
            # Wait for message ID callback
            ret = self.bot.botLayer.ctxMap[ctxId]["event"].wait(
                int(options["waitMsgId"])
            )
            if not ret:
                return "TIMEOUT"
            else:
                msgId = self.bot.botLayer.getContextValue(ctxId, "msgId")
                del self.bot.botLayer.ctxMap[ctxId]
                return msgId

    
    async def sendMsgDirect(self,cmdParams,options):
        to,message,*other = cmdParams
        context_info = ContextInfoAttributes()

        if "disappearing" in options:
            context_info.expiration = int(options["disappearing"])*86400
            context_info.ephemeral_setting_timestamp = int(time.time())
            context_info.disappearing_mode = DisappearingModeAttributes(
                initiator=DisappearingModeAttributes.INITIATOR_CHANGED_IN_CHAT,
                trigger=DisappearingModeAttributes.TRIGGER_CHAT_SETTING,
                initiatedByMe=True
            )
        else:
            context_info.expiration = 0
            context_info.ephemeral_setting_timestamp = int(time.time())
            context_info.disappearing_mode = DisappearingModeAttributes(
                initiator=DisappearingModeAttributes.INITIATOR_CHANGED_IN_CHAT,
                trigger=DisappearingModeAttributes.TRIGGER_UNKNOWN,
                initiatedByMe=None
            )

        if "source" in options:
            if options["source"]=="random":
                srcs = ["contact_card","contact_search","global_search_new_chat","phone_number_hyperlink"]
                source = random.choice(srcs)
            else:
                #"group_participant_list"
                source = options["source"]

            context_info.entry_point_conversion_app ="whatsapp"
            context_info.entry_point_conversion_source = source
            context_info.entry_point_conversion_delay_seconds = random.randint(5,13)

        if "url" in options:
            url = options["url"]                    
            urlTitle = options["urltitle"] if "urltitle" in options else None
            urlDesc = options["urldesc"] if "urldesc" in options else None
            
            attr = ExtendedTextAttributes(
                text = message,            
                matched_text = url,
                description= urlDesc,
                title = urlTitle,
                context_info= context_info
            )     
        elif "bjid" in options:
            context_info.forwarding_score=2
            context_info.is_forwarded=True
            context_info.business_message_forward_info=BusinessMessageForwardInfoAttributes(
                        business_owner_jid=Jid.normalize(options["bjid"])
                    )              
            attr = ExtendedTextAttributes(
                text = message,
                preview_type=0,
                context_info= context_info,
                invite_link_group_type_v2=0
            )   
        else:        
            attr = ExtendedTextAttributes(                
                text = message,
                preview_type=0,
                context_info= context_info,
                invite_link_group_type_v2=0
            )            

        messageEntity = ExtendedTextMessageProtocolEntity(attr, 
            MessageMetaAttributes(id=self.bot.idType,recipient=Jid.normalize(to),timestamp=int(time.time()))            
        )        

        self.bot.botLayer.ackQueue.append(messageEntity.getId())

        if "broadcast" in options:
            #广播@broadcast发送            
            self.logger.info("Send broadcast msg (ID=%s)" % messageEntity.getId())           
            messageEntity.to = options["bcid"]
            messageEntity.phash = options["phash"]            
            await self.bot.botLayer.toLower(messageEntity)    
        else:
            self.logger.info("Send Msg (ID=%s)" % messageEntity.getId())
            target = Jid.normalize(to.split(",")[0])
            if target.endswith("@g.us"):
                entity = OutgoingChatstateProtocolEntity(ChatstateProtocolEntity.STATE_TYPING, target,Jid.normalize(self.bot.botId))
            else:
                entity = OutgoingChatstateProtocolEntity(ChatstateProtocolEntity.STATE_TYPING, target)
            await self.bot.botLayer.toLower(entity)
            time.sleep(1)

            await self.bot.botLayer.toLower(messageEntity)   


        if "waitMsgId" in options:
            self.bot.botLayer.ctxMap[options["ctxId"]]["msgId"] = messageEntity.getId()
            self.bot.botLayer.ctxMap[options["ctxId"]]["event"].set()            
        
        return messageEntity.getId()   