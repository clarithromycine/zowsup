"""msg.revoke command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_messages.protocolentities.message_protocol import ProtocolMessageProtocolEntity
from core.layers.protocol_messages.protocolentities.attributes.attributes_protocol import ProtocolAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_message_key import MessageKeyAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from core.common.tools import Jid
import time

logger = logging.getLogger(__name__)


class Cmd_Msg_Revoke(BotCommand):

    COMMAND = "msg.revoke"
    DESCRIPTION = "Revoke a message"


    async def execute(self, params, options):

        attr = ProtocolAttributes(
            key=MessageKeyAttributes(
                id=params[1],
                from_me=True,
                remote_jid=Jid.normalize(params[0])                
            ),
            type=ProtocolAttributes.TYPE_REVOKE
        )
        messageEntity = ProtocolMessageProtocolEntity(attr,
            MessageMetaAttributes(
                id=self.bot.idType,
                recipient=Jid.normalize(params[0]),
                timestamp=int(time.time()),
                edit="7"
            )            
        )
        await self.bot.botLayer.toLower(messageEntity)
        return "JUSTWAIT"


    
