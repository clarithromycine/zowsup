"""misc.bizintegrity command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import WmexQueryIqProtocolEntity, WmexResultIqProtocolEntity
from core.common.tools import Jid
import uuid
import json
import asyncio

logger = logging.getLogger(__name__)



class Cmd_Account_SetUserName(BotCommand):

    COMMAND = "account.setusername"
    DESCRIPTION = "set the username of account"    

    async def execute(self, params, options):

        session_id = str(uuid.uuid4())

        query = {            
            "variables":{
                "reserved":True,
                "session_id":session_id,
                "source":"USER_INPUT",
                "username":params[0]
            }                    
        }        
        try:
            entity = WmexQueryIqProtocolEntity(query_name="UsernameSet", query_obj=query)
            entity_result = await self.send_iq_expect(entity,WmexResultIqProtocolEntity)
            result = entity_result.result_obj            
            return self.success(result=result)
            
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))  



