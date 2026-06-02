"""contact.getdevices command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_contacts.protocolentities import DevicesGetSyncIqProtocolEntity, DevicesResultSyncIqProtocolEntity
from core.common.tools import Jid

logger = logging.getLogger(__name__)


class Cmd_Contact_GetDevices(BotCommand):
    COMMAND = "contact.getdevices"
    DESCRIPTION = "Get contact devices"

    async def execute(self, params, options):

        try:
            entity = DevicesGetSyncIqProtocolEntity(jids=Jid.normalize(params[0]).split(","))
            result = await self.send_iq_expect(entity, DevicesResultSyncIqProtocolEntity)
            return self.success(
                devices = result.devicesDict,
            )

        except Exception as e:
            logger.error(f"getDevices error: {e}")
            return self.fail(error=str(e))


