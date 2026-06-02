"""group.info command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_groups.protocolentities import InfoGroupsIqProtocolEntity, InfoGroupsResultIqProtocolEntity
from core.common.tools import Jid

logger = logging.getLogger(__name__)


class Cmd_Group_Info(BotCommand):
    
    COMMAND = "group.info"
    DESCRIPTION = "Get group information"


    async def execute(self, params, options):
        try:
            entity = InfoGroupsIqProtocolEntity(group_jid=Jid.normalize(params[0]))
            result = await self.send_iq_expect(entity, InfoGroupsResultIqProtocolEntity)
            logger.info(f"{self.COMMAND} success")
            return self.success(
                groupId = result.groupId,
                subject = result.subject,
                participants = result.participants,
                participant_lids = result.participant_lids,
            )

        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e)) 


