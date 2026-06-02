"""group.getinvite command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_groups.protocolentities import (
    GetInviteCodeGroupsIqProtocolEntity,
    SuccessGetInviteCodeGroupsIqProtocolEntity
)
from core.common.tools import Jid

logger = logging.getLogger(__name__)


class Cmd_Group_GetInvite(BotCommand):

    COMMAND = "group.getinvite"
    DESCRIPTION = "Get group invite code"


    async def execute(self, params, options):
        """
        Get the group invite code for sharing.
        
        Params: group_jid
        
        Returns: dict with groupJid and inviteCode
        
        Previous location: ZowBotLayer.getGroupInvite()
        """
        to = params[0]
        
        try:
            entity = GetInviteCodeGroupsIqProtocolEntity(group_jid=Jid.normalize(to))
            result = await self.send_iq_expect(entity, SuccessGetInviteCodeGroupsIqProtocolEntity)
            logger.info(f"{self.COMMAND} success")
            return self.success(
                groupJid = result.groupJid,
                inviteCode = result.inviteCode
            )
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e)) 


