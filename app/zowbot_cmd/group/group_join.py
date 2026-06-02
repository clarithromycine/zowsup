"""group.join command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_groups.protocolentities import JoinWithCodeGroupsIqProtocolEntity,SuccessJoinWithCodeGroupsIqProtocolEntity


logger = logging.getLogger(__name__)



class Cmd_Group_Join(BotCommand):

    COMMAND = "group.join"
    DESCRIPTION = "Join group with invite code"
    
    async def execute(self, params, options):

        try:
            entity = JoinWithCodeGroupsIqProtocolEntity(code=params[0])
            result = await self.send_iq_expect(entity,SuccessJoinWithCodeGroupsIqProtocolEntity)
            logger.info(f"{self.COMMAND} success")
            return self.success(group_jid=result.groupId)
        
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e)) 


