"""misc.reachouttimelock command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import WmexQueryIqProtocolEntity, WmexResultIqProtocolEntity

logger = logging.getLogger(__name__)


class Cmd_Misc_Removetimelock(BotCommand):


    COMMAND = "misc.removetimelock"
    DESCRIPTION = "Remove reach out time lock"


    async def execute(self, params, options):
        """
        Remove reach out time lock information.        
        """
        try:
            query_obj = {
                "variables": {
                    "input": {
                         "violation_type":"SPAM",
                         "reason":"User watched remediation video",
                         "reachout_timelock_type":"BIZ_QUALITY"
                    },
                }
            }
            entity = WmexQueryIqProtocolEntity(
                query_name="RemoveAccountReachoutTimelock",
                query_obj=query_obj
            )
            result = await self.send_iq_expect(entity, WmexResultIqProtocolEntity)                        
            print(result)
            return self.success(
                result = result.result_obj["data"],                
            )
            
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))   


