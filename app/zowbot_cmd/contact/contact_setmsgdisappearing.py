"""contact.setmsgdisappearing command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
import time
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_messages.protocolentities.message_protocol import ProtocolMessageProtocolEntity
from core.layers.protocol_messages.protocolentities.attributes.attributes_protocol import ProtocolAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_message_key import MessageKeyAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_disappearing_mode import DisappearingModeAttributes
from core.layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from core.layers.protocol_iq.protocolentities import ResultIqProtocolEntity
from core.common.tools import Jid

logger = logging.getLogger(__name__)


class Cmd_Contact_SetMsgDisappearing(BotCommand):

    COMMAND = "contact.setmsgdisappearing"
    DESCRIPTION = "Set message disappearing for contact"


    async def execute(self, params, options):

        if len(params) == 1:
            disappearingTime = 86400  # 1 day
        else:
            disappearingTime = int(params[1]) * 86400
        
        try:
            attr = ProtocolAttributes(
                key=MessageKeyAttributes(
                    id=None,
                    from_me=True,
                    remote_jid=Jid.normalize(params[0])                
                ),
                type=ProtocolAttributes.TYPE_EPHEMERAL_SETTING,
                ephemeral_expiration=disappearingTime,
                disappearing_mode=DisappearingModeAttributes(
                    trigger=DisappearingModeAttributes.TRIGGER_CHAT_SETTING,
                    initiatedByMe=True,
                ),
                timestamp_ms=int(time.time()*1000)
            )
            entity = ProtocolMessageProtocolEntity(
                protocol_attr=attr,
                message_meta_attributes=MessageMetaAttributes(
                    id=self.bot.idType, 
                    recipient=Jid.normalize(params[0]), 
                    timestamp=int(time.time())
                )
            )
            result = await self.send_iq_expect(entity, ResultIqProtocolEntity)
            return self.success()
        
        except Exception as e:
            logger.error(f"setContactMsgDisappearing error: {e}")
            return self.fail(error=str(e))


