"""account.info command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import AccountInfoIqProtocolEntity, AccountInfoResultIqProtocolEntity

logger = logging.getLogger(__name__)

class Cmd_Account_Info(BotCommand):
    COMMAND = "account.info"
    DESCRIPTION = "Get account information"
    async def execute(self, params, options):

        try:
            entity = AccountInfoIqProtocolEntity()
            result = await self.send_iq_expect(entity, AccountInfoResultIqProtocolEntity)

            return self.success(
                creation=result.creation,
                lastReg=result.lastReg
            )

        except Exception as e:
            logger.error(f"accountInfo error: {e}")
            return self.fail(error=str(e))

