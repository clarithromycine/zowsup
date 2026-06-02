"""misc.reachouttimelock command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import WmexQueryIqProtocolEntity, WmexResultIqProtocolEntity

logger = logging.getLogger(__name__)


class Cmd_Misc_Reachouttimelock(BotCommand):


    COMMAND = "misc.reachouttimelock"
    DESCRIPTION = "Get reach out time lock"


    async def execute(self, params, options):
        """
        Get reach out time lock information.
        
        Returns: dict with reachout timelock status
        
        Previous location: ZowBotLayer.reachOutTimeLock()
        """
        try:
            query_obj = {
                "variables": {
                    "input": {},
                }
            }
            entity = WmexQueryIqProtocolEntity(
                query_name="FetchReachoutTimelockQuery",
                query_obj=query_obj
            )
            result = await self.send_iq_expect(entity, WmexResultIqProtocolEntity)
            timelock_data = result.result_obj["data"]["xwa2_fetch_account_reachout_timelock"]
            return self.success(
                is_active = timelock_data["is_active"],
                timelock_end = timelock_data["time_enforcement_ends"]
            )
            
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))   


