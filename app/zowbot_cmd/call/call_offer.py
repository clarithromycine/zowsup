"""msg.edit command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.common.tools import Jid

logger = logging.getLogger(__name__)

class Cmd_Call_Offer(BotCommand):

    COMMAND = "call.offer"
    DESCRIPTION = "Offer a call to a user"


    async def execute(self, params, options):
        
        jid = Jid.normalize(params[0])        
        
        from voip.voip_adapter import get_voip_adapter
        voip = get_voip_adapter()
        voip.register_bot(self.bot.botId, self.bot)

        # ── Start the call via VoIP module ──
        result = await voip.start_call(self.bot.botId, jid)
        if "error" in result:
            return self.fail(result["error"])
        
        return self.success(
            callId=result["call_id"],
            state=result.get("state", "unknown"),
        )


