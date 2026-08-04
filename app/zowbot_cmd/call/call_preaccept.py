"""call.preaccept command — send preaccept to acknowledge an incoming call."""

import logging
from typing import Any

from app.zowbot_cmd.base import BotCommand
from core.common.tools import Jid
from core.layers.protocol_calls.protocolentities.call_preaccept import PreacceptCallProtocolEntity
from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes

logger = logging.getLogger(__name__)


class Cmd_Call_Preaccept(BotCommand):
    """
    Send a preaccept stanza to acknowledge an incoming call.

    WhatsApp sends preaccept automatically before accept to signal
    that the callee is preparing the media path.

    Usage:
        call.preaccept <peer_jid> <call_id> <call_creator_jid>

    Example:
        call.preaccept 8619874406144@s.whatsapp.net 00A1B... 8619874406144@s.whatsapp.net
    """

    COMMAND = "call.preaccept"
    DESCRIPTION = "Send preaccept stanza to acknowledge incoming call"

    async def execute(self, params, options):
        self.require_params(params, 3)

        peer_jid = Jid.normalize(params[0])
        call_id = params[1]
        call_creator_jid = Jid.normalize(params[2])

        preaccept_entity = PreacceptCallProtocolEntity(
            callId=call_id,
            callCreator=call_creator_jid,
            netMedium="3",
            callMetaAttributes=CallMetaAttributes(
                id=self.bot.idType,
                recipient=peer_jid,
            ),
        )

        await self.bot.botLayer.toLower(preaccept_entity)
        logger.info("Preaccept sent: call_id=%s", call_id)
        return {"retcode": 0, "result": {"callId": call_id}}
