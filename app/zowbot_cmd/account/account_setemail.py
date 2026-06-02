"""account.setemail command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities.email import SetEmailIqProtocolEntity
from app.param_not_enough_exception import ParamsNotEnoughException
from core.layers.protocol_iq.protocolentities.email.iq_email_result import EmailResultIqProtocolEntity

logger = logging.getLogger(__name__)


class Cmd_Account_SetEmail(BotCommand):

    COMMAND = "account.setemail"
    DESCRIPTION = "Set email"

    async def execute(self, params, options):

        if len(params) == 0:
            raise ParamsNotEnoughException()
        
        email = params[0]
        
        try:
            entity = SetEmailIqProtocolEntity(email=email)
            result = await self.send_iq_expect(entity, EmailResultIqProtocolEntity)

            return self.success()
        
        except Exception as e:
            logger.error(f"setEmail error: {e}")
            return self.fail(error=str(e))



