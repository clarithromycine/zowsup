"""group.list command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from unittest import result
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_groups.protocolentities import ListGroupsIqProtocolEntity, ListGroupsResultIqProtocolEntity

logger = logging.getLogger(__name__)


class Cmd_Group_List(BotCommand):
    
    COMMAND = "group.list"
    DESCRIPTION = "List groups"


    async def execute(self, params, options):
        """
        List all groups for current account.
        
        Returns: dict with groups list and count
        
        Previous location: ZowBotLayer.listGroups()
        """
        try:
            entity = ListGroupsIqProtocolEntity(participants=True)
            result= await self.send_iq_expect(entity, ListGroupsResultIqProtocolEntity)

            groups = []
            for group in result.getGroups():
                groups.append({
                    "id": group.getId(),
                    "subject": group.getSubject(),
                    "creator": group.getCreator(),
                    "subjectOwner": group.getSubjectOwner(),
                    "subjectTime": group.getSubjectTime(),
                    "creationTime": group.getCreationTime(),
                    "participants": group.getParticipants()
                })

            logger.info(f"{self.COMMAND} success")
            return self.success(
                groups = groups,
                count = len(groups)
            )
            
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e)) 



