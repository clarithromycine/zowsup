"""call.transport command — send transport stanza after accepting a call."""

import logging
from typing import Any

from app.zowbot_cmd.base import BotCommand
from core.common.tools import Jid
from core.layers.protocol_calls.protocolentities.call_transport import TransportCallProtocolEntity
from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes

logger = logging.getLogger(__name__)


class Cmd_Call_Transport(BotCommand):
    """
    Send a transport stanza to trigger relay info exchange.

    Usage:
        call.transport <peer_jid> <call_id> <call_creator_jid>

    This should be sent after call.accept to prompt the call creator
    to send back relay endpoint information.

    Example:
        call.transport 8619874406144@s.whatsapp.net 00A1B... 8619874406144@s.whatsapp.net
    """

    COMMAND = "call.transport"
    DESCRIPTION = "Send transport stanza to trigger relay info"

    async def execute(self, params, options):
        self.require_params(params, 3)

        peer_jid = Jid.normalize(params[0])
        call_id = params[1]
        call_creator_jid = Jid.normalize(params[2])

        transport_entity = TransportCallProtocolEntity(
            callId=call_id,
            callCreator=call_creator_jid,
            netMedium="2",
            netProtocol="0",
            transportMessageType="1",
            p2pCandRound="1",
            callMetaAttributes=CallMetaAttributes(
                id=self.bot.idType,
                recipient=peer_jid,
            ),
        )

        await self.bot.botLayer.toLower(transport_entity)
        logger.info("Transport sent: call_id=%s", call_id)
        return {"retcode": 0, "result": {"callId": call_id}}
