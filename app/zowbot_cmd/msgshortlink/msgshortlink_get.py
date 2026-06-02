"""msgshortlink.get command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import GetShortLinkIqProtocolEntity, GetShortLinkResultIqProtocolEntity

logger = logging.getLogger(__name__)



class Cmd_Msgshortlink_Get(BotCommand):

    COMMAND = "msgshortlink.get"
    DESCRIPTION = "Get message short link"


    async def execute(self, params, options):

        try:
            entity = GetShortLinkIqProtocolEntity()
            result = await self.send_iq_expect(entity, GetShortLinkResultIqProtocolEntity)
            return self.success(
                    code = result.code,
                    link = "https://wa.me/message/" + result.code,
                    msg = result.msg
            )

        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))  

