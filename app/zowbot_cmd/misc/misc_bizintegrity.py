"""misc.bizintegrity command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import WmexQueryIqProtocolEntity, WmexResultIqProtocolEntity
from core.common.tools import Jid

logger = logging.getLogger(__name__)



class Cmd_Misc_Bizintegrity(BotCommand):

    COMMAND = "misc.bizintegrity"
    DESCRIPTION = "Integrity check"    

    async def execute(self, params, options):

        user_ids = params[0].split(",")        
        jids = []
        for id in user_ids:
            jids.append({"jid": Jid.normalize(id)})
        
        query = {
            "variables": {
                "input": {
                    "query_input": jids,
                    "telemetry": {
                        "context": "INTERACTIVE"
                    }                    
                }
            }
        }
        
        try:
            entity = WmexQueryIqProtocolEntity(query_name="BizIntegrityQuery", query_obj=query)
            entity_result = await self.send_iq_expect(entity,WmexResultIqProtocolEntity)

            result = []                                
            for obj in entity_result.result_obj["data"]["xwa2_fetch_wa_users"]:
                logger.debug("integrity check obj: %s", obj)
                if "integrity_signals_info" in obj and "phone_country_code" in obj["integrity_signals_info"]:
                    result.append({
                        "jid": obj["jid"],
                        "country": obj["integrity_signals_info"]["phone_country_code"],    
                        "is_business": (obj["__typename"] == "XWA2BusinessUser"),                        
                        "is_suspicious": obj["integrity_signals_info"]["is_suspicious"],                            
                        "trust_tier": obj["integrity_signals_info"]["trust_tier"]
                    })
                else:
                    result.append({
                        "jid": obj["jid"],
                        "not_found": True
                    })

            return self.success(result=result)
            
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))  



