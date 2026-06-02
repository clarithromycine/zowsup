"""account.set2fa command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import Set2FAIqProtocolEntity
from core.layers.protocol_iq.protocolentities import ResultIqProtocolEntity

logger = logging.getLogger(__name__)



class Cmd_Account_Set2FA(BotCommand):

    COMMAND = "account.set2fa"
    DESCRIPTION = "Set two-factor authentication"

    async def execute(self, params, options):

        if len(params) == 0:
            params = [self.bot.botId[-6:], self.bot.botId + "@163.com"]

        try :
            entity = Set2FAIqProtocolEntity(code=params[0], email=params[1])
            result = await self.send_iq_expect(entity, ResultIqProtocolEntity)
            return self.success()
        except Exception as e:
            logger.error(f"set2FA error: {e}")
            return self.fail(error=str(e))


