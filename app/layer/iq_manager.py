"""IqManager — IQ request/response lifecycle with Future-based async support."""

import asyncio
import logging
import time

from proto import zowsup_pb2
from core.common import YowConstants
from core.layers.protocol_iq.protocolentities import (
    ResultIqProtocolEntity,
    ErrorIqProtocolEntity,
    IqProtocolEntity,
    MultiDevicePairIqProtocolEntity,
    MultiDevicePairSuccessIqProtocolEntity,
    MultiDevicePairCompanionHelloIqProtocolEntity,
    MultiDevicePairSignIqProtocolEntity,
)
logger = logging.getLogger(__name__)


class IqManager:
    """Manages IQ request sending, response matching, heartbeat, and pairing IQ dispatch."""

    def __init__(self, layer):
        """
        Args:
            layer: ZowBotLayer instance
        """
        self.layer = layer

    async def send_iq_async(self, entity):
        """Send an IQ entity and await its response (delegates to layer.sendIqAsync).

        Returns:
            dict: {"result": entity_result, "original_iq": original_iq}
        Raises:
            asyncio.TimeoutError: if no response within 30s.
            IqErrorException: if the peer responds with an IQ error stanza.
        """
        try:
            return await self.layer.sendIqAsync(entity)
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(
                f"IQ response timeout for entity {entity.getId()}"
            )

    async def on_iq(self, entity):
        """Handle incoming IQ stanzas — heartbeat, results, errors, and pairing."""

        if self.layer.getProp("TRANSFER6_MODE", False):
            if time.time() - self.layer.bot.startts > 300:
                # TRANSFER6 mode timeout — force quit
                self.layer.bot.quit()

        self.layer.pingCount += 1
        if self.layer.pingCount % 10 == 0:
            self.layer.callback(event={"event": zowsup_pb2.BotEvent.Event.HEARTBEAT})

        if isinstance(entity, ResultIqProtocolEntity):
            self.layer.setCmdResult(entity.getId(), {"status": "ok"})
            return

        if isinstance(entity, ErrorIqProtocolEntity):
            self.layer.setCmdError(entity.getId(), entity.code)
            return

        # ── Pairing IQ dispatch → PairingManager ────────────────────────
        if isinstance(entity, MultiDevicePairIqProtocolEntity):
            await self.layer.pairing.handle_pair_iq(entity)
            return

        if isinstance(entity, MultiDevicePairSuccessIqProtocolEntity):
            await self.layer.pairing.handle_pair_success_iq(entity)
            return
