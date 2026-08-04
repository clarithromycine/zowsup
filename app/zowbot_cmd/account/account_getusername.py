"""misc.bizintegrity command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import WmexQueryIqProtocolEntity, WmexResultIqProtocolEntity
from core.common.tools import Jid

logger = logging.getLogger(__name__)



class Cmd_Misc_GetUserName(BotCommand):

    COMMAND = "account.getusername"
    DESCRIPTION = "get the username of account"    

    async def execute(self, params, options):
                
        query = {
            "variables": {}
        }
        
        try:
            entity = WmexQueryIqProtocolEntity(query_name="UsernameGet", query_obj=query)
            entity_result = await self.send_iq_expect(entity,WmexResultIqProtocolEntity)

            name = None
            if "data" in entity_result.result_obj and entity_result.result_obj["data"]:
                name = entity_result.result_obj["data"]["xwa2_username_get"]["username"]
            
            return self.success(name=name)
            
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))  



