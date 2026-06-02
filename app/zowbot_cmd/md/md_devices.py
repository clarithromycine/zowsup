"""md.devices command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.common.tools import Jid
from core.layers.protocol_contacts.protocolentities import DevicesGetSyncIqProtocolEntity,DevicesResultSyncIqProtocolEntity

logger = logging.getLogger(__name__)



class Cmd_Md_Devices(BotCommand):
    COMMAND = "md.devices"
    DESCRIPTION = "Get self devices"
    async def execute(self, params, options):        
        try:            
            entity = DevicesGetSyncIqProtocolEntity(jids=[Jid.normalize(self.bot.botId)])
            result = await self.send_iq_expect(entity, DevicesResultSyncIqProtocolEntity)
            
            logger.info("getDevices success")
            return self.success(
                devices = result.devicesDict
            )
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))

