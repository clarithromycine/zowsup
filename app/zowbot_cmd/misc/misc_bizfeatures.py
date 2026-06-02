"""misc.bizfeatures command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import GetBusinessFeatureIqProtocolEntity, GetBusinessFeatureResultIqProtocolEntity

logger = logging.getLogger(__name__)



class Cmd_Misc_Bizfeatures(BotCommand):

    COMMAND = "misc.bizfeatures"
    DESCRIPTION = "Get business features"


    async def execute(self, params, options):

        try:
            entity = GetBusinessFeatureIqProtocolEntity()
            result = await self.send_iq_expect(entity, GetBusinessFeatureResultIqProtocolEntity)
            return self.success(
                marketingMessages = result.marketingMessages,
                metaVerified = result.metaVerified,
                genai = result.genai
            )
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))   

