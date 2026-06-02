"""msg.sendinteractive command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
import json
import time
from app.zowbot_cmd.base_send import BotSendCommand
from core.layers.protocol_media.protocolentities import RequestMediaConnIqProtocolEntity, ResultRequestMediaConnIqProtocolEntity
from core.layers.protocol_chatstate.protocolentities import OutgoingChatstateProtocolEntity, ChatstateProtocolEntity
from core.layers.protocol_messages.protocolentities import InteractiveMessageProtocolEntity
from core.layers.protocol_messages.protocolentities.attributes.attributes_interactive import InteractiveAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_interactive_header import InteractiveHeaderAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from core.common.tools import Jid

logger = logging.getLogger(__name__)


class Cmd_Msg_Sendinteractive(BotSendCommand):

    COMMAND = "msg.sendinteractive"
    DESCRIPTION = "Send interactive message"


    async def execute(self, params, options):

        to, body, *others = params
        bot= self.bot
        
        header = None
        if "header" in options:
            header = json.loads(options["header"])
        
        footer = None
        if "footer" in options:
            footer = options["footer"]
        
        buttons = None
        if "buttons" in options:
            buttons = [
                {
                    "name": "cta_url",
                    "params_json": '{"display_text":"More Details","url":"https://mmg.whatsapp.net/v/t62.7114-24/571013301_922343627119311_2190867036823974143_n.enc?ccb=11-4&oh=01_Q5Aa3gEdfDrdYbHab3Cg35KMwNj2J8ygEI1DxHDf1qVGaykJgA&oe=69A1572A&_nc_sid=5e03e0&mms3=true"}'
                }
            ]
                        
        try :
            entity_result = None
            if header is not None and ("image" in header or "video" in header or "document" in header):
                entity = RequestMediaConnIqProtocolEntity()
                entity_result = await self.send_iq_expect(entity,ResultRequestMediaConnIqProtocolEntity)                                            

            target = Jid.normalize(to.split(",")[0])
            if target.endswith("@g.us"):
                entity = OutgoingChatstateProtocolEntity(ChatstateProtocolEntity.STATE_TYPING, target,Jid.normalize(self.bot.botId))
            else:
                entity = OutgoingChatstateProtocolEntity(ChatstateProtocolEntity.STATE_TYPING, target)
            await self.bot.botLayer.toLower(entity)
            time.sleep(1) 
            
            attr = InteractiveAttributes(
                body=body,
                header=InteractiveHeaderAttributes.fromJson(header, entity_result),
                footer=footer,
                buttons=buttons                
            )
            messageEntity = InteractiveMessageProtocolEntity(
                attr, 
                MessageMetaAttributes(id=bot.botLayer.idType, recipient=Jid.normalize(to), timestamp=int(time.time()))
            )
            
            bot.botLayer.ackQueue.append(messageEntity.getId())
            bot.botLayer.toLower(messageEntity)    

                                                    
        except Exception as e:
            logger.error(f"Request media connection failed: {e}")
            return self.fail(error=str(e))
                    
        return "JUSTWAIT"
    


