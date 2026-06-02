"""misc.prekeycount command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.axolotl.protocolentities.iq_key_count import GetKeysCountIqProtocolEntity, ResultKeyCountIqProtocolEntity

logger = logging.getLogger(__name__)


class Cmd_Misc_Prekeycount(BotCommand):

    COMMAND = "misc.prekeycount"
    DESCRIPTION = "Query the prekey count from server"


    async def execute(self, params, options):

        try:
            # Use the layer's _sendIqAsync method to send the IQ\
            entity = GetKeysCountIqProtocolEntity()
            result = await self.send_iq_expect(entity, ResultKeyCountIqProtocolEntity)
            return self.success(count=result.count)                
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))   


