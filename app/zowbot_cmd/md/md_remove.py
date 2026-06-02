"""md.remove command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import MultiDeviceRemoveCompanionDeviceIqProtocolEntity,ResultIqProtocolEntity
from core.common.tools import Jid

logger = logging.getLogger(__name__)


class Cmd_Md_Remove(BotCommand):
    COMMAND = "md.remove"
    DESCRIPTION = "Remove multi-device"


    async def execute(self, params, options):

        try :
            if len(params) == 0 or params[0] == "all":
                entity = MultiDeviceRemoveCompanionDeviceIqProtocolEntity(jid=None)  # Remove all
            else:
                entity = MultiDeviceRemoveCompanionDeviceIqProtocolEntity(jid=Jid.normalize(params[0]))

            result = await self.send_iq_expect(entity,ResultIqProtocolEntity)
            return self.success()
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))            


