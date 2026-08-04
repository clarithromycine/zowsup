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
import time,os
from core.layers.protocol_calls.protocolentities.call_terminate import TerminateCallProtocolEntity
from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes
from proto import e2e_pb2
from axolotl.protocol.whispermessage import WhisperMessage

logger = logging.getLogger(__name__)


class Cmd_Call_Terminate(BotCommand):

    COMMAND = "call.terminate"
    DESCRIPTION = "Terminate a call"

    async def execute(self, params, options):

        callEntity = TerminateCallProtocolEntity(            
            callId=params[1],
            callCreator=self.bot.profile.config.lid,                                      
            callMetaAttributes=CallMetaAttributes(
                id=self.bot.idType,
                recipient=Jid.normalize(params[0]),                                
            )            
        )
        
        await self.bot.botLayer.toLower(callEntity)
        return "JUSTWAIT"


