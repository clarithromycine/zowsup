"""misc.checkactive command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.axolotl.protocolentities.iq_key_get import GetKeysIqProtocolEntity
from core.layers.axolotl.protocolentities.iq_keys_get_result import ResultGetKeysIqProtocolEntity
from core.common.tools import Jid

logger = logging.getLogger(__name__)


class Cmd_Misc_Checkactive(BotCommand):


    COMMAND = "misc.checkactive"
    DESCRIPTION = "Check active"


    async def execute(self, params, options):
        """
        Check if contacts are active.
        
        Params: comma-separated list of JIDs
        Returns: dict with userActiveMap
        
        Previous location: ZowBotLayer.checkActive()
        """
        bot = self.bot
        try:
            bot.botLayer.setProp("CHECKNUM_MODE", True)
            entity = GetKeysIqProtocolEntity(
                [Jid.normalize(c) for c in params[0].split(',')],
                _id=bot.idType
            )
            result = await self.send_iq_expect(entity,ResultGetKeysIqProtocolEntity)

            return self.success(
                 result = result.userActiveMap
            )
                
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))   

