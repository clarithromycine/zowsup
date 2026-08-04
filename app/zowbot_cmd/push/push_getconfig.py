"""account.init command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import PushGetIqProtocolEntity, PushGetResultIqProtocolEntity

logger = logging.getLogger(__name__)

class Cmd_Push_Getconfig(BotCommand):
    COMMAND = "push.getconfig"
    DESCRIPTION = "Get firebase push config info"

    async def execute(self, params, options):
        try:
            push = PushGetIqProtocolEntity()        
            result = await self.send_iq_expect(push,PushGetResultIqProtocolEntity)
            return self.success(pkey=result.pkey,id = result.pushId,platform = result.platform)            

        except Exception as e:
            return self.fail(error=str(e))  
                
