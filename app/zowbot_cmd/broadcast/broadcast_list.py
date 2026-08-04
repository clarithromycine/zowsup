"""account.init command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import GetBroadcastListProtocolEntity,GetBroadcastListResultProtocolEntity

logger = logging.getLogger(__name__)



class Cmd_Broadcast_List(BotCommand):
    COMMAND = "broadcast.list"
    DESCRIPTION = "Get broadcast list"


    async def execute(self, params, options):
        try:
            entity = GetBroadcastListProtocolEntity()
            result = await self.send_iq_expect(entity, GetBroadcastListResultProtocolEntity)

            return self.success(broadcast_lists=result.broadcastLists)
               
        except Exception as e:
            return self.fail(error=str(e))
