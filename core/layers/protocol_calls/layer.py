from ...layers import YowProtocolLayer
from typing import Optional, Any, List, Dict, Union
from .protocolentities import *
from ...layers.protocol_acks.protocolentities import OutgoingAckProtocolEntity
from ...layers.protocol_receipts.protocolentities import OutgoingReceiptProtocolEntity
import logging
logger = logging.getLogger(__name__)

class YowCallsProtocolLayer(YowProtocolLayer):

    def __init__(self) -> None:
        handleMap = {
            "call": (self.recvCall, self.sendCall)
        }
        super().__init__(handleMap)

    def __str__(self):
        return "call Layer"

    async def sendCall(self, entity) -> Any:
        if entity.getTag() == "call":
            node = entity.toProtocolTreeNode()
            logger.info("SEND call: type=%s, call_id=%s, to=%s",
                        entity.getType(), entity.getCallId(), entity.getTo())
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("SEND call node: %s", node)
            await self.toLower(node)

    async def recvCall(self, node) -> Any:
        entity = CallProtocolEntity.fromProtocolTreeNode(node)                
        call_type = entity.getType()
        logger.info("RECV call: type=%s, call_id=%s, from=%s",
                     call_type, entity.getCallId(), entity.getFrom())
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("RECV call node: %s", node)

        if call_type == "offer":
            entity = OfferCallProtocolEntity.fromProtocolTreeNode(node, db=self.getStack().getProp("profile").axolotl_manager)
            await self.toUpper(entity)
            receipt = OutgoingReceiptProtocolEntity(node["id"], node["from"], callId = entity.getCallId(), callCreator = entity.getCallCreator())
            await self.toLower(receipt.toProtocolTreeNode())

        elif call_type == "accept":
            # Decrypt callKey from accept stanza
            entity = AcceptCallProtocolEntity.fromProtocolTreeNode(
                node, db=self.getStack().getProp("profile").axolotl_manager
            )
            await self.toUpper(entity)
            ack = OutgoingAckProtocolEntity(node["id"], "call", "accept", node["from"])
            await self.toLower(ack.toProtocolTreeNode())

        elif call_type == "transport":
            entity = TransportCallProtocolEntity.fromProtocolTreeNode(node)
            await self.toUpper(entity)
            ack = OutgoingAckProtocolEntity(node["id"], "call", "transport", node["from"])
            await self.toLower(ack.toProtocolTreeNode())

        elif call_type == "preaccept":
            entity = PreacceptCallProtocolEntity.fromProtocolTreeNode(node)
            ack = OutgoingAckProtocolEntity(node["id"], "call", "preaccept", node["from"])
            await self.toLower(ack.toProtocolTreeNode())
            await self.toUpper(entity)

        elif call_type == "terminate":
            entity = TerminateCallProtocolEntity.fromProtocolTreeNode(node)
            await self.toUpper(entity)
            ack = OutgoingAckProtocolEntity(node["id"], "call", "terminate", node["from"])
            await self.toLower(ack.toProtocolTreeNode())

        elif call_type == "mute_v2":
            # mute_v2: send ack + notify upper layer
            ack = OutgoingAckProtocolEntity(node["id"], "call", "mute_v2", node["from"])
            await self.toLower(ack.toProtocolTreeNode())
            await self.toUpper(entity)

        elif call_type == "duration":
            # duration: call statistics sent at call end — ack only
            ack = OutgoingAckProtocolEntity(node["id"], "call", "duration", node["from"])
            await self.toLower(ack.toProtocolTreeNode())

        elif call_type == "relaylatency":
            # relaylatency: ack + forward to upper (call_manager handles via handle_relaylatency)
            entity = RelayLatencyCallProtocolEntity.fromProtocolTreeNode(node)
            ack = OutgoingAckProtocolEntity(node["id"], "call", "relaylatency", node["from"])
            await self.toLower(ack.toProtocolTreeNode())
            await self.toUpper(entity)

        else:
            # reject / mute / unknown — generic handling
            ack = OutgoingAckProtocolEntity(node["id"], "call", None, node["from"])
            await self.toLower(ack.toProtocolTreeNode())
            await self.toUpper(entity)


        

