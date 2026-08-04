


"""misc.prekeycount command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities.privacy.iq_get_privacy import GetPrivacyIqProtocolEntity, ResultPrivacyIqProtocolEntity

logger = logging.getLogger(__name__)


class Cmd_Misc_GetPrivacy(BotCommand):

    COMMAND = "misc.getprivacy"
    DESCRIPTION = "Query the privacy settings from server"

    async def execute(self, params, options):

        try:
            # Use the layer's _sendIqAsync method to send the IQ\
            entity = GetPrivacyIqProtocolEntity()
            result = await self.send_iq_expect(entity, ResultPrivacyIqProtocolEntity)
            return self.success(privacy=result.setting)                
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))   