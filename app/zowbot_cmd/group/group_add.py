"""group.add command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_groups.protocolentities import (
    AddParticipantsIqProtocolEntity,
    SuccessAddParticipantsIqProtocolEntity
)
from core.common.tools import Jid

logger = logging.getLogger(__name__)


class Cmd_Group_Add(BotCommand):
    COMMAND = "group.add"
    DESCRIPTION = "Add member to group"

    async def execute(self, params, options):

        try:
            entity = AddParticipantsIqProtocolEntity(
                group_jid=Jid.normalize(params[0]),
                participantList=Jid.normalize(params[1]).split(",")
            )
            result = await self.send_iq_expect(entity, SuccessAddParticipantsIqProtocolEntity)
        
            return self.success(
                successCount = len(result.successList),
                successJids = result.successList,
                errorCount = len(result.errorList),
                errorJids = result.errorList    
            )

        except Exception as e:
            logger.error(f"groupadd error: {e}")
            return self.fail(error=str(e)) 


