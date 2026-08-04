"""call.accept command — accept an incoming VoIP call."""

import logging
import os
from typing import Any

from app.zowbot_cmd.base import BotCommand
from core.common.tools import Jid
from core.layers.protocol_calls.protocolentities.call_accept import AcceptCallProtocolEntity
from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes
from proto import e2e_pb2

logger = logging.getLogger(__name__)


class Cmd_Call_Accept(BotCommand):
    """
    Accept an incoming VoIP call.

    Usage:
        call.accept <call_creator_jid> <call_id> [call_key_hex]

    Params:
        call_creator_jid  — JID of the call creator (who initiated the call)
        call_id           — WhatsApp call ID from the incoming offer
        call_key_hex      — (optional) 32-byte call key as hex string;
                             if omitted, a new random call key is generated

    After accepting, the call creator's device will receive the accept stanza
    and the media relay negotiation will begin.

    Example:
        call.accept 8619874406144:0@s.whatsapp.net 00A1B2C3D4E5F6789012345678ABCDEF
    """

    COMMAND = "call.accept"
    DESCRIPTION = "Accept an incoming VoIP call"

    async def execute(self, params, options):
        self.require_params(params, 2)

        call_creator_jid = Jid.normalize(params[0])
        call_id = params[1]
        call_key = None

        # Optional: explicit call key (32 bytes hex)
        if len(params) >= 3 and params[2]:
            try:
                call_key = bytes.fromhex(params[2])
                if len(call_key) != 32:
                    return self.fail(
                        f"Invalid call key length: {len(call_key)} bytes, expected 32"
                    )
            except ValueError:
                return self.fail(f"Invalid hex string for call_key: {params[2]}")

        if call_key is None:
            call_key = os.urandom(32)

        accept_entity = AcceptCallProtocolEntity(
            callId=call_id,
            callCreator=call_creator_jid,
            callKey=call_key,
            callMetaAttributes=CallMetaAttributes(
                id=self.bot.idType,
                recipient=call_creator_jid,
            ),
            db=self.bot.botLayer.db,
        )

        await self.bot.botLayer.toLower(accept_entity)
        logger.info(
            "Call accepted: call_id=%s, creator=%s",
            call_id, call_creator_jid,
        )
        return self.success(
            callId=call_id,
            callCreator=call_creator_jid,
        )

    def success(self, **fields):
        return {"retcode": 0, "result": fields}

    def fail(self, reason: str):
        return {"retcode": -1, "error": reason}
