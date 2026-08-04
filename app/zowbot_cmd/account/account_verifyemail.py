"""account.verifyemail command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import VerifyEmailIqProtocolEntity

logger = logging.getLogger(__name__)



class Cmd_Account_VerifyEmail(BotCommand):
    COMMAND = "account.verifyemail"
    DESCRIPTION = "Verify email address"
    async def execute(self, params, options):

        try:
            entity = VerifyEmailIqProtocolEntity()
            result = await self.send_iq_expect(entity, VerifyEmailIqProtocolEntity)

            logger.info("verifyEmail success")
            return self.success()
        
        except Exception as e:
            logger.error(f"verifyEmail error: {e}")
            return self.fail(error=str(e))

