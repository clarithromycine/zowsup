"""account.init command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import GetBroadcastLimitationProtocolEntity,GetBroadcastLimitationResultProtocolEntity

logger = logging.getLogger(__name__)



class Cmd_Broadcast_Limitation(BotCommand):
    COMMAND = "broadcast.limitation"
    DESCRIPTION = "Get broadcast limitation"


    async def execute(self, params, options):
        try:
            entity = GetBroadcastLimitationProtocolEntity()
            result = await self.send_iq_expect(entity, GetBroadcastLimitationResultProtocolEntity)

            return self.success(
                messages_left=result.messagesLeft,
                total_limit=result.totalLimit,
                is_heavy_sender=result.isHeavySender,
                start_ts=result.startTs,
                end_ts=result.endTs,
                reset_ts=result.resetTs,
            )

        except Exception as e:
            return self.fail(error=str(e))
