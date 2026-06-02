"""msgshortlink.decode command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import DecodeShortLinkIqProtocolEntity, DecodeShortLinkResultIqProtocolEntity

logger = logging.getLogger(__name__)


class Cmd_Msgshortlink_decode(BotCommand):

    COMMAND = "msgshortlink.decode"
    DESCRIPTION = "Decode message short link"


    async def execute(self, params, options):

        try:
            entity = DecodeShortLinkIqProtocolEntity(code=params[0])
            result = await self.send_iq_expect(entity, DecodeShortLinkResultIqProtocolEntity)
            return self.success(
                msg = result.msg,
                jid = result.jid,
                verified_name = result.verified_name,
                is_signed = result.is_signed,
                verified_level = result.verified_level
            )
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))  

