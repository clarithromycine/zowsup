"""group.leave command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_groups.protocolentities import (
    LeaveGroupsIqProtocolEntity,
    SuccessLeaveGroupsIqProtocolEntity
)
from core.common.tools import Jid

logger = logging.getLogger(__name__)


class Cmd_Group_Leave(BotCommand):
    
    COMMAND = "group.leave"
    DESCRIPTION = "Leave a group"

    async def execute(self, params, options):
        """
        Leave (exit) a group.
        
        Params: group_jid
        
        Returns: dict with retcode 0 on success
        
        Previous location: ZowBotLayer.leaveGroup()
        """
        try:
            groupJid = params[0]
            entity = LeaveGroupsIqProtocolEntity([Jid.normalize(groupJid)])
            result_dict = await self.send_iq_expect(entity, SuccessLeaveGroupsIqProtocolEntity)
            logger.info(f"{self.COMMAND} success")
            return self.success()
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))  
