"""group.approve command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_groups.protocolentities import (
    ApproveParticipantsGroupsIqProtocolEntity
)
from core.layers.protocol_iq.protocolentities import ResultIqProtocolEntity
from core.common.tools import Jid

logger = logging.getLogger(__name__)


class Cmd_Group_Approve(BotCommand):

    COMMAND = "group.approve"
    DESCRIPTION = "Approve group join request"
    
    async def execute(self, params, options):

        if len(params) >= 3:
            action = params[2]
        else:
            action = "approve"

        try:        
            entity = ApproveParticipantsGroupsIqProtocolEntity(
                group_jid=Jid.normalize(params[0]),
                participantList=Jid.normalize(params[1]).split(","),
                action=action
            )
            result = await self.send_iq_expect(entity, ResultIqProtocolEntity)
            logger.info("groupApprove success")
            return self.success()
        except Exception as e:
            logger.error(f"groupApprove error: {e}")
            return self.fail(error=str(e)) 

