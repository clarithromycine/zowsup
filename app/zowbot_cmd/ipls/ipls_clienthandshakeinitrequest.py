"""contact.list command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import WmexQueryIqProtocolEntity, WmexResultIqProtocolEntity
from core.common.tools import Jid
from app.param_not_enough_exception import ParamsNotEnoughException
import os,base64

logger = logging.getLogger(__name__)


class Cmd_Iplst_ClientHandshakeInitRequest(BotCommand):

    COMMAND = "ipls.clienthandshakeinitrequest"
    DESCRIPTION = "IPLS init handshake"


    '''
    <iq to='s.whatsapp.net' xmlns='w:mex' type='get' id='058'>
        <trace><flow_id>25523747957257182</flow_id></trace>
        <query query_id='25523747957257182'>
            {"queryId":"25523747957257182","variables":{"request_type":"GET","session_id":"4kSQSCuVGpG+qO6\/lxBkKC2vs5fqiIatohbxym7NZzc="}}
        </query>
    </iq>

    '''

    async def execute(self, params, options):

        if len(params) == 0:
            raise ParamsNotEnoughException()
        
        try:
                        
            session_id = os.urandom(32)
            query = {                
                "variables": {
                    "request_type": params[0],
                    "session_id": base64.b64encode(session_id).decode(),
                }
            }

            entity = WmexQueryIqProtocolEntity(query_name="IplsClientHandshakeInitRequest", query_obj=query)
            result = await self.send_iq_expect(entity, WmexResultIqProtocolEntity)
            print(result.result_obj)
            return self.success(
                server_hello_payload=result.result_obj["data"]["xwa2_ipls_client_init"]["server_hello_payload"],
                session_id = base64.b64encode(session_id).decode()
            )
        
        except Exception as e:
            logger.error(f"getContactList error: {e}")
            return self.fail(error=str(e))




