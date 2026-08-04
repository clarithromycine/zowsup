
import asyncio
import logging

logger = logging.getLogger(__name__)


class CallHandler:
    """Handles VoIP call stanza sending and incoming ack/receipt dispatch."""

    def __init__(self, layer):
        """
        Args:
            layer: ZowBotLayer instance
        """
        self.layer = layer
        # stanza ID → Future, for send_call_query responses
        self._pending_queries: dict[str, asyncio.Future] = {}
    

    async def send_call_node(self, entity):        
        await self.layer.toLower(entity)

    async def send_call_query(self, entity):

        stanza_id = entity.getId()
        if not stanza_id:
            logger.warning("CallHandler: send_call_query — entity has no id")
            await self.layer.toLower(entity)
            return None

        loop = self.layer.getStack().getLoop()
        future = loop.create_future() if loop else asyncio.Future()
        self._pending_queries[stanza_id] = future
        await self.layer.toLower(entity)
        try:
            return await asyncio.wait_for(future, timeout=30)
        except asyncio.TimeoutError:
            self._pending_queries.pop(stanza_id, None)
            logger.warning("CallHandler: send_call_query timeout (30s, id=%s)", stanza_id)
            return None

    # ── Incoming ack / receipt ─────────────────────────────────────────────

    async def on_ack(self, entity):

        ack_class = entity.getClass()
        ack_type = entity.getType()
        ack_id = entity.getId()

        logger.debug("CallHandler: ack class=%s type=%s id=%s from=%s",
                     ack_class, ack_type, ack_id,
                     getattr(entity, 'getFrom', lambda: '?')())

        if ack_class != "call":
            return

        logger.info("CallHandler: call ack type=%s id=%s", ack_type, ack_id)

        # Resolve any pending send_call_query waiting for this ack
        pending = self._pending_queries.pop(ack_id, None)
        if pending and not pending.done():
            pending.set_result(entity)

        if ack_type == "offer":
            await self._handle_offer_ack(entity)

    async def on_receipt(self, entity):

        logger.debug("CallHandler: receipt id=%s from=%s",
                     entity.getId(), entity.getFrom())

    # ── Internal ───────────────────────────────────────────────────────────

    async def _handle_offer_ack(self, entity):
        
        node = getattr(entity, "_original_node", None)
        if node is None:
            logger.warning("CallHandler: no _original_node on ack entity")
            return

        relay_node = node.getChild("relay")
        if not relay_node:
            return

        try:
            from voip.signaling.parser import parse_relay_from_ack
            from voip.voip_adapter import get_voip_adapter

            parsed = parse_relay_from_ack(node)
            if not parsed.relays:
                logger.warning("CallHandler: offer ack had <relay> but no endpoints parsed")
                return

            logger.info("CallHandler: relay from offer ack: %d endpoints", len(parsed.relays))


            voip = get_voip_adapter()
            mgr = voip._get_manager(self.layer.bot.botId)

            # Extract call_id from ack entity or child node attributes
            call_id = ""
            if hasattr(entity, 'getCallId'):
                call_id = entity.getCallId() or ""
            if not call_id and node:
                for child in (node.getAllChildren() or []):
                    cid = child.getAttributeValue("call-id") if hasattr(child, 'getAttributeValue') else None
                    if cid:
                        call_id = cid
                        break

            session = mgr.get_session(call_id) if call_id else None
            if not session and call_id:
                # Session may not exist if call was started via call.offer command
                session = mgr._create_session(call_id)
                mgr._wire_session_callbacks(session)
                mgr._sessions[call_id] = session

            if session and session.call and not session.call.is_ended():
                session.call.relay_data = {
                    "relays": parsed.relays,
                    "participant_jids": parsed.participant_jids,
                    "participants": parsed.participants,
                    "uuid": parsed.uuid,
                    "self_pid": parsed.self_pid,
                    "peer_pid": parsed.peer_pid,
                    "hbh_key": parsed.hbh_key,
                    "rte": parsed.rte,
                }
                session._relay.set_ssrc(session._self_ssrc)
                session._relay.set_pids(
                    parsed.self_pid or 0,
                    parsed.peer_pid or 0,
                )
                session._connect_relays(parsed.relays)
                logger.info("CallHandler: relay connected: %d endpoints", len(parsed.relays))

        except Exception as e:
            logger.error("CallHandler: relay parse failed: %s", e)