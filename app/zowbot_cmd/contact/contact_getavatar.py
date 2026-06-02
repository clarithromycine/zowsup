"""account.getavatar — get avatar for self or a contact."""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
from app.zowbot_cmd.base import BotCommand
from core.common.tools import Jid
from core.layers.protocol_profiles.protocolentities import (
    GetPictureIqProtocolEntity,
    ResultGetPictureIqProtocolEntity,
)

class Cmd_Contact_GetAvatar(BotCommand):
    COMMAND = "contact.getavatar"
    DESCRIPTION = "Get contact avatar"

    async def execute(self,params, options):

        try:
            self.require_params(params, 1)
            jid = self.get_param(params, 0, None)
            entity = GetPictureIqProtocolEntity(jid=Jid.normalize(jid), preview=False)
            result = await self.send_iq_expect(entity, ResultGetPictureIqProtocolEntity)
            return self.success(
                id=result.getPictureId(),
                type=result.getPictureType(),
                url=result.getUrl(),
            )
        except Exception as e:
            self.logger.error(f"getAvatar error for target {jid}: {e}")
            return self.fail(error=str(e))

