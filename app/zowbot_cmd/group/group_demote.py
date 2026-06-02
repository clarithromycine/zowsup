"""group.demote command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_groups.protocolentities import (
    DemoteParticipantsIqProtocolEntity
)
from core.layers.protocol_iq.protocolentities import ResultIqProtocolEntity
from core.common.tools import Jid

logger = logging.getLogger(__name__)


class Cmd_Group_Demote(BotCommand):

    COMMAND = "group.demote"
    DESCRIPTION = "Demote admin to member"

    async def execute(self, params, options):

        try:        
            entity = DemoteParticipantsIqProtocolEntity(
                group_jid=Jid.normalize(params[0]),
                participantList=Jid.normalize(params[1]).split(",")
            )
            result = await self.send_iq_expect(entity, ResultIqProtocolEntity)
            logger.info("groupDemote success")
            return self.success()

        except Exception as e:
            logger.error(f"groupDemote error: {e}")
            return self.fail(error=str(e)) 

