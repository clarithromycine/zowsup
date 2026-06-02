"""group.create command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_groups.protocolentities import (
    CreateGroupsIqProtocolEntity,
    SuccessCreateGroupsIqProtocolEntity
)
from core.common.tools import Jid

logger = logging.getLogger(__name__)


class Cmd_Group_Create(BotCommand):

    COMMAND = "group.create"
    DESCRIPTION = "Create a new group"

    async def execute(self, params, options):

        if len(params) != 2:
            raise Exception("Invalid params: group_name and participants required")
        
        if params[1] == "":
            logger.info("create an empty group")
            pList = None
        else:
            pList = Jid.normalize(params[1]).split(",")
        
        try:
            entity = CreateGroupsIqProtocolEntity(
                params[0],
                participants=pList,
                creator=self.bot.botId
            )
            result = await self.send_iq_expect(entity, SuccessCreateGroupsIqProtocolEntity)
            logger.info("makegroup success")
            return {"groupId": result.groupId}
        except Exception as e:
            logger.error(f"createGroup error: {e}")
            return self.fail(error=str(e)) 


