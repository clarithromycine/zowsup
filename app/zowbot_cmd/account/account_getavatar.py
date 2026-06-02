"""account.getavatar — get avatar for self or a contact."""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
from app.zowbot_cmd.base import BotCommand
from core.common.tools import Jid
from core.layers.protocol_profiles.protocolentities import GetPictureIqProtocolEntity,ResultGetPictureIqProtocolEntity

class Cmd_Account_Getavatar(BotCommand):
    COMMAND = "account.getavatar"
    DESCRIPTION = "Get self avatar"

    async def execute(self, params, options):
        
        jid = self.get_param(params, 0, self.bot.botId)
        entity = GetPictureIqProtocolEntity(jid=Jid.normalize(jid), preview=False)
        try:
            result = await self.send_iq_expect(entity, ResultGetPictureIqProtocolEntity)
            return self.success(
                id=result.getPictureId(),
                type=result.getPictureType(),
                url=result.getUrl(),
            )
        except Exception as e:
            self.logger.error(f"getAvatar error for target {jid}: {e}")
            return self.fail(error=str(e))

