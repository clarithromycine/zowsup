"""account.verifyemailcode command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import VerifyEmailCodeIqProtocolEntity, EmailResultIqProtocolEntity

logger = logging.getLogger(__name__)


class Cmd_Account_VerifyEmailCode(BotCommand):
    
    COMMAND = "account.verifyemailcode"
    DESCRIPTION = "Verify email code"


    async def execute(self, params, options):

        try:
            entity = VerifyEmailCodeIqProtocolEntity(code=params[0])
            result = await self.send_iq_expect(entity, EmailResultIqProtocolEntity)
            return self.success()

        except Exception as e:
            logger.error(f"verifyEmailCode error: {e}")
            return self.fail(error=str(e))


