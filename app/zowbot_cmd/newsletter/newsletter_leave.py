"""newsletter.leave command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import WmexQueryIqProtocolEntity, WmexResultIqProtocolEntity
from app.param_not_enough_exception import ParamsNotEnoughException

logger = logging.getLogger(__name__)



class Cmd_Newsletter_Leave(BotCommand):

    COMMAND = "newsletter.leave"
    DESCRIPTION = "Leave newsletter"

    async def execute(self, params, options):

        if len(params) < 1:
            raise ParamsNotEnoughException()
        
        try:
            newsletter_id = params[0]
            query = {
                "variables": {
                    "jid": newsletter_id
                }
            }
            entity = WmexQueryIqProtocolEntity(
                query_name="NewsletterLeave",
                query_obj=query
            )
            entity_result = await self.send_iq_expect(entity, WmexResultIqProtocolEntity)
            return self.success(
                result=entity_result.result_obj
            )
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))   


