"""group.remove command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_groups.protocolentities import (
    RemoveParticipantsIqProtocolEntity,
    SuccessRemoveParticipantsIqProtocolEntity
)
from core.common.tools import Jid

logger = logging.getLogger(__name__)


class Cmd_Group_Remove(BotCommand):

    COMMAND = "group.remove"
    DESCRIPTION = "Remove member from group"


    async def execute(self, params, options):

        try:
            entity = RemoveParticipantsIqProtocolEntity(
                group_jid=Jid.normalize(params[0]),
                participantList=Jid.normalize(params[1]).split(",")
            )
            result = await self.send_iq_expect(entity, SuccessRemoveParticipantsIqProtocolEntity)
            logger.info(f"{self.COMMAND} success")
            return self.success()
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))
              

