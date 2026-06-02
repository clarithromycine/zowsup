"""contact.trust command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
import time
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import TrustContactIqProtocolEntity, ResultIqProtocolEntity
from core.common.tools import Jid

logger = logging.getLogger(__name__)


class Cmd_Contact_Trust(BotCommand):

    COMMAND = "contact.trust"
    DESCRIPTION = "Trust a contact"

    async def execute(self, params, options):

        try:
            entity = TrustContactIqProtocolEntity(Jid.normalize(params[0]), int(time.time()))
            result = await self.send_iq_expect(entity, ResultIqProtocolEntity)
            logger.info("trust contact success")
            return self.success()
        except Exception as e:
            logger.error(f"trust contact error: {e}")
            return self.fail(error=str(e))

