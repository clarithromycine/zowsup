"""misc.bizintegrity command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import WmexQueryIqProtocolEntity, WmexResultIqProtocolEntity
import uuid
import time

logger = logging.getLogger(__name__)



class Cmd_WWW_GetCertificates(BotCommand):

    COMMAND = "www.getcertificates"
    DESCRIPTION = "Get WWW certificates"

    async def execute(self, params, options):
        # Read persisted trace_id matching APK's C35881jE.A01(false)
        reg_trace = getattr(self.bot.botLayer, "_canonical_reg_trace_id", None)
        if not reg_trace:
            reg_trace = str(uuid.uuid4())
            self.bot.botLayer._canonical_reg_trace_id = reg_trace

        query = {
            "variables": {
                "input": {
                    "registration_trace_id": reg_trace,
                    "request_id": str(uuid.uuid4()),
                    "request_time": str(int(time.time())),
                    "use_case":"CANONICAL"
                }
            }
        }
        
        try:
            entity = WmexQueryIqProtocolEntity(query_name="WWWGetCertificates", query_obj=query)
            entity_result = await self.send_iq_expect(entity,WmexResultIqProtocolEntity)

            result = []                                
            print(entity_result.result_obj)
            return self.success(result=result)
            
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))  
        



