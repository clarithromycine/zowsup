"""contact.list command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import WmexQueryIqProtocolEntity, WmexResultIqProtocolEntity
from core.common.tools import Jid
from app.param_not_enough_exception import ParamsNotEnoughException

logger = logging.getLogger(__name__)


class Cmd_Contact_List(BotCommand):

    COMMAND = "contact.list"
    DESCRIPTION = "Get contact list"


    async def execute(self, params, options):

        if len(params) == 0:
            raise ParamsNotEnoughException()
        
        try:
            query = {
                "variables": {
                    "batch_size": 3000,
                    "include_encrypted_metadata_v2": False,
                    "include_lid_info": True,
                    "input": {
                        "query_input": [{"jid": Jid.normalize(params[0])}],
                        "telemetry": {"context": "REGISTRATION"}
                    }
                }
            }
            entity = WmexQueryIqProtocolEntity(query_name="SelfContactsQuery", query_obj=query)
            result = await self.send_iq_expect(entity, WmexResultIqProtocolEntity)
            return self.success(
                result=result.result_obj
            )
        
        except Exception as e:
            logger.error(f"getContactList error: {e}")
            return self.fail(error=str(e))




