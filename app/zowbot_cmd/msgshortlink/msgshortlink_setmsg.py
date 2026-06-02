"""msgshortlink.setmsg command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import SetMsgShortLinkIqProtocolEntity, SetMsgShortLinkResultIqProtocolEntity

logger = logging.getLogger(__name__)


class Cmd_Msgshortlink_Setmsg(BotCommand):

    COMMAND = "msgshortlink.setmsg"
    DESCRIPTION = "Set message in short link"

    async def execute(self, params, options):

        try:
            entity = SetMsgShortLinkIqProtocolEntity(code=params[0], msg=params[1])
            result = await self.send_iq_expect(entity, SetMsgShortLinkResultIqProtocolEntity)
            return self.success()
        
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))  