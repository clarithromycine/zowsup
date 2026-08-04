


"""misc.prekeycount command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities.privacy.iq_get_privacy import ResultPrivacyIqProtocolEntity
from core.layers.protocol_iq.protocolentities.privacy.iq_set_privacy import SetPrivacyIqProtocolEntity

logger = logging.getLogger(__name__)


class Cmd_Misc_SetPrivacy(BotCommand):

    COMMAND = "misc.setprivacy"
    DESCRIPTION = "Set the privacy settings on the server"

    async def execute(self, params, options):

        try:
            # Use the layer's _sendIqAsync method to send the IQ\
            entity = SetPrivacyIqProtocolEntity(name=params[0], value=params[1])            
            result = await self.send_iq_expect(entity, ResultPrivacyIqProtocolEntity)
            return self.success(privacy=result.setting)                
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))   