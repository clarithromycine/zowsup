"""account.getemail command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities.email import GetEmailIqProtocolEntity,EmailResultIqProtocolEntity

logger = logging.getLogger(__name__)

class Cmd_Account_Getemail(BotCommand):
    COMMAND = "account.getemail"
    DESCRIPTION = "Get email"
    async def execute(self,params, options):
        try:
            entity = GetEmailIqProtocolEntity()
            result = await self.send_iq_expect(entity, EmailResultIqProtocolEntity)
            return self.success(
                emailAddress=result.emailAddress,
                verified=result.verified,
                confirmed=result.confirmed
            )
        except Exception as e:
            logger.error(f"getEmail error: {e}")
            return self.fail(error=str(e))

