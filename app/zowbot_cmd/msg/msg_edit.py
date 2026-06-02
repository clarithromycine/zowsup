"""msg.edit command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_messages.protocolentities.message_protocol import ProtocolMessageProtocolEntity
from core.layers.protocol_messages.protocolentities.attributes.attributes_protocol import ProtocolAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_message_key import MessageKeyAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_message import MessageAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_extendedtext import ExtendedTextAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_context_info import ContextInfoAttributes
from core.common.tools import Jid
import time

logger = logging.getLogger(__name__)


class Cmd_Msg_Edit(BotCommand):

    COMMAND = "msg.edit"
    DESCRIPTION = "Edit a message"

    async def execute(self, params, options):

        attr = ProtocolAttributes(
            key=MessageKeyAttributes(
                id=params[1],
                from_me=True,
                remote_jid=Jid.normalize(params[0])                
            ),
            type=ProtocolAttributes.TYPE_MESSAGE_EDIT,            
            edited_message=MessageAttributes(
                extended_text=ExtendedTextAttributes(
                    text=params[2],            
                    preview_type=0,
                    context_info=ContextInfoAttributes()
                )
            ),
            timestamp_ms=int(time.time()*1000)
        )        
        messageEntity = ProtocolMessageProtocolEntity(attr,
            MessageMetaAttributes(
                id=self.bot.idType,
                recipient=Jid.normalize(params[0]),
                timestamp=int(time.time()),
                edit="1"
            )            
        )
        await self.bot.botLayer.toLower(messageEntity)
        return "JUSTWAIT"


