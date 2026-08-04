"""
CallSession — single-call lifecycle orchestrator.

All state in this class is per-call. Multiple CallSession instances
can coexist within a single CallManager (multi-call support).

Ties together signaling (Phase 1), media (Phase 2+4), and transport (Phase 3)
into a complete WhatsApp VoIP call.

Reference: WaCalls internal/voip/call/callmanager.go
"""

import asyncio
import logging
import math
import time
from array import array
from typing import Optional, Callable

from .call_state import (
    CallInfo, CallState, CallDirection, EndReason, Transition, InvalidTransition,
)
from ..media.codec import Codec, OpusCodec, MLowCodec, NullCodec
from ..media.rtp import RtpSession
from ..media.srtp import SrtpContext
from ..media.encryption import generate_call_key, derive_per_jid_srtp_key, derive_warp_auth_key
from ..media.ssrc import generate_secure_ssrc
from ..media.pipeline import TxPipeline, RxPipeline
from ..transport.relay import RelayManager, RelayConfig


class CallError(Exception):
    def __init__(self, msg: str):
        super().__init__(msg)


class CallSession:
    """
    Manages the complete lifecycle of a single WhatsApp VoIP call.

    All fields are per-call — no cross-call state leakage.
    Created by CallManager when a new call starts (offer/accept).
    Destroyed when the call ends (terminate/reject/timeout).
    """

    # ── SILENT MODE: disable ALL audio TX (keepalive + feed) after connect ──
    SILENT_MODE: bool = False

    # ── Echo test: disabled ──
    _echo_test: bool = False

    def __init__(
        self,
        call_id: str,
        bot=None,
        logger: logging.Logger = None,
    ):
        self._log = logger or logging.getLogger(__name__)
        self._call_id = call_id

        # ── zowsup integration hooks (extracted from bot) ──
        if bot is not None:
            from core.layers.axolotl.props import PROP_IDENTITY_AUTOTRUST
            self._send_query = bot.botLayer._send_call_query
            self._send_node = bot.botLayer._send_call_node
            self._send_iq = bot.botLayer._sendIqAsync
            self._own_jid = getattr(bot.profile.config, 'lid', bot.botId + "@s.whatsapp.net")
            self._db = bot.botLayer.db
            self._autotrust = bot.botLayer.getProp(PROP_IDENTITY_AUTOTRUST, False)
            self._id_type = bot.idType
        else:
            self._send_query = None
            self._send_node = None
            self._send_iq = None
            self._own_jid = ""
            self._db = None
            self._autotrust = False
            self._id_type = None

        # ── Call identity ──
        self._call: Optional[CallInfo] = None

        # ── Media components (created per-call) ──
        self._encode_codec: Optional[Codec] = None  # TX: Opus(SMPL) if available, else MLow
        self._decode_codec: Optional[Codec] = None  # RX: always MLow (peer sends MLow frames)
        self._rtp_session: Optional[RtpSession] = None
        self._srtp_send: Optional[SrtpContext] = None
        self._srtp_recv: Optional[SrtpContext] = None
        self._relay: RelayManager = RelayManager(logger)
        self._tx: Optional[TxPipeline] = None
        self._rx: Optional[RxPipeline] = None

        # ── SSRC ──
        self._self_ssrc: int = 0
        self._peer_ssrcs: list[int] = []

        # ── P2P fallback (direct UDP to peer) ──
        self._peer_p2p_candidates: list[dict] = []
        self._p2p_socket: Optional[object] = None  # socket.socket
        self._p2p_enabled: bool = True  # set False to disable P2P test

        # ── State tracking ──
        self._first_packet_sent: bool = False
        self._accepted_by_jid: str = ""
        self._last_capture_at: float = 0.0
        self._keepalive_task: Optional[asyncio.Task] = None

        # ── Callbacks (set by CallManager) ──
        self.on_state_change: Optional[Callable[["CallSession", CallInfo], None]] = None
        self.on_incoming: Optional[Callable[["CallSession", CallInfo], None]] = None
        self.on_ended: Optional[Callable[["CallSession", CallInfo], None]] = None
        self.on_peer_audio: Optional[Callable[["CallSession", list[float]], None]] = None

        # ── WAV recording buffer: array('f') = 4B/sample (vs 24B Python float) ──
        self._recv_pcm = array('f')

        # ── Diagnostic counters (all initialized to clean state) ──
        self._audio_frame_cnt = 0
        self._first_rtp_ts: Optional[int] = None
        self._recv_pcm_pos = 0
        self._silence_frame = array('f', [0.0]) * 960
        self._raw_cnt = 0
        self._raw_pkt_cnt = 0
        self._echo_filtered_cnt = 0
        self._nonstun_cnt = 0
        self._bc_cnt = 0
        self._silence_cnt = 0
        self._peer_ssrc_observed = False
        self._first_packet_log = True
        self._had_relay_data = False
        self._srtp_accepted_by = ""
        self._echo_frame = b""
        self._last_raw_mlow = b""
        self._echo_rms_logged = False
        self._mlow_dump = None
        self._mlow_dump_count = 0

        # ── Relay callbacks ──
        self._relay.set_on_connected(self._on_relay_connected)
        self._relay.set_on_connect_failed(self._on_relay_connect_failed)
        self._relay.set_on_receive(self._on_relay_data)

    # ── Properties ──────────────────────────────────────────────

    @property
    def call_id(self) -> str:
        return self._call_id

    @property
    def call(self) -> Optional[CallInfo]:
        return self._call

    @property
    def _has_relay(self) -> bool:
        return self._relay.has_connection()

    def is_active(self) -> bool:
        """Check if this session has an active (non-ended) call."""
        return self._call is not None and not self._call.is_ended()

    # ── Outgoing call ──────────────────────────────────────────

    async def start_call(self, peer_jid: str, is_video: bool = False) -> str:
        """Initiate an outgoing call. Returns the call_id."""
        from .call_manager import _generate_call_id, _ensure_device_jid
        
        call_id = _generate_call_id()
        self._call_id = call_id
        creator = _ensure_device_jid(self._own_jid)
        peer_q = _ensure_device_jid(peer_jid)
        self._self_ssrc = generate_secure_ssrc(call_id, creator, 0)
        peer_ssrc = generate_secure_ssrc(call_id, peer_q, 0)
        self._peer_ssrcs = [peer_ssrc]

        call_key = generate_call_key()
        call = CallInfo.new_outgoing(call_id, peer_jid, creator)
        call.encryption_key = call_key
        self._call = call

        self._init_codec()
        self._rtp_session = RtpSession.whatsapp_opus(self._self_ssrc)
        self._first_packet_sent = False

        self._log.info("decrypt_params: enc_key=%s device_jid=%s ssrc=%d",
                       call_key.hex(), creator, self._self_ssrc)

        if self._send_query:
            try:
                offer_node = await self._build_offer_node(call_id, call_key, peer_jid)
                ack_node = await self._send_query(offer_node)
                if ack_node is not None:
                    self._handle_call_ack(ack_node)
            except Exception as e:
                self._log.error("start_call failed: %s", e)
                call.apply_transition(Transition.TERMINATED, EndReason.FAILED)
                self._emit_state()
                raise CallError(str(e)) from e

        call.apply_transition(Transition.OFFER_SENT)
        self._emit_state()
        self._log.info("Call offer sent: %s → %s", call_id, peer_jid)
        return call_id

    async def _build_offer_node(self, call_id: str, call_key: bytes, peer_jid: str):
        """Build the outgoing OfferCallProtocolEntity.

        Handles device JID discovery, E2E session assurance, and entity
        construction — all within the voip module via voip.signaling.builder.
        """
        from ..signaling.builder import build_offer_stanza
        return await build_offer_stanza(
            call_id=call_id,
            call_key=call_key,
            peer_jid=peer_jid,
            own_jid=self._own_jid,
            send_iq=self._send_iq,
            db=self._db,
            autotrust=self._autotrust,
            id_type=self._id_type,
        )

    def _handle_call_ack(self, ack_node):
        """Process offer ack containing relay information."""
        from ..signaling.parser import parse_relay_from_ack

        # ── Unwrap: ack entity → raw ProtocolTreeNode (_original_node) ──
        original = getattr(ack_node, "_original_node", None)
        if original is not None:
            ack_node = original

        children = getattr(ack_node, "children", []) or []
        child_tags = [(getattr(c, "tag", "?"), len(getattr(c, "data", b"") or b""))
                      for c in children]
        self._log.warning("ACK NODE: tag=%s children=%s",
                         getattr(ack_node, "tag", "?"), child_tags)

        node = ack_node
        tag = getattr(node, "tag", "")
        if tag in ("iq", "call"):
            inner_children = getattr(node, "children", []) or []
            if len(inner_children) == 1:
                inner = inner_children[0]
                inner_tag = getattr(inner, "tag", "")
                if inner_tag in ("ack", "offer"):
                    self._log.info("ACK NODE: unwrapping %s → inner %s", tag, inner_tag)
                    node = inner

        parsed = parse_relay_from_ack(node)

        self._log.warning("ACK PARSED: relays=%d rte=%s uuid=%s",
                         len(parsed.relays),
                         parsed.rte[:20].hex() if parsed.rte else "EMPTY",
                         parsed.uuid)

        if not parsed.relays:
            return

        self._log.info("Offer ack: %d relays, %d participants",
                       len(parsed.relays), len(parsed.participant_jids))

        call = self._call
        if not call:
            return

        call.relay_data = {
            "relays": parsed.relays,
            "participant_jids": parsed.participant_jids,
            "participants": parsed.participants,  # list[ParticipantInfo] with pid
            "uuid": parsed.uuid,
            "self_pid": parsed.self_pid,
            "peer_pid": parsed.peer_pid,
            "hbh_key": parsed.hbh_key,
            "rte": parsed.rte,
        }

        if parsed.participant_jids:
            self._refine_ssrcs_from_participants(parsed.participant_jids,
                                                  parsed.participants)
            self._relay.set_ssrc(self._self_ssrc)
            # Subscribe to ALL peer SSRCs (primary + companion devices)
            self._relay.set_subscription_ssrcs(self._peer_ssrcs)

        if parsed.self_pid is not None or parsed.peer_pid is not None:
            # ── PID semantics in ack (outgoing call) ──
            # The ack sender (callee) sets:
            #   self_pid = callee's own PID
            #   peer_pid = caller's PID (recipient of ack = us)
            # Participants = caller's devices (our devices).
            # From our (caller's) perspective:
            #   self_pid should be our PID   → parsed.peer_pid
            #   peer_pid should be callee's  → parsed.self_pid
            self._relay.set_pids(
                parsed.peer_pid or 0,  # our PID (caller)
                parsed.self_pid or 0,  # callee's PID
            )
            self._log.info("Relay PIDs set (outgoing): self=%d peer=%d",
                           parsed.peer_pid or 0, parsed.self_pid or 0)
            self._relay.resend_subscriptions()

        if self._self_ssrc == 0:
            from .call_manager import _ensure_device_jid
            self._self_ssrc = generate_secure_ssrc(call.call_id, _ensure_device_jid(self._own_jid), 0)
            self._peer_ssrcs = [generate_secure_ssrc(call.call_id, _ensure_device_jid(call.peer_jid), 0)]
            self._relay.set_ssrc(self._self_ssrc)
            self._relay.set_subscription_ssrcs(self._peer_ssrcs)
            self._log.info("SSRC initialized from call_id: self=%d peer=%d",
                           self._self_ssrc, self._peer_ssrcs[0])

        if call.encryption_key:
            self._init_srtp_keys()

        self._connect_relays(parsed.relays)

    # ── Incoming call ──────────────────────────────────────────

    def handle_call_offer(self, offer_entity) -> None:
        """Handle an incoming call offer from zowsup."""
        from .call_manager import _ensure_device_jid

        call_id = offer_entity.getCallId()
        peer_jid = offer_entity.getFrom()
        creator = offer_entity.getCallCreator() or peer_jid
        self._call_id = call_id

        # ── Send preaccept IMMEDIATELY (before any heavy work) ──
        if self._send_node:
            from ..signaling.builder import build_preaccept_stanza
            try:
                pa = build_preaccept_stanza(peer_jid, call_id, creator)
                asyncio.ensure_future(self._send_node(pa))
                self._log.info("Preaccept sent immediately for call %s", call_id)
            except Exception as e:
                self._log.error("Preaccept build/send failed: %s", e)

        self._self_ssrc = generate_secure_ssrc(call_id, _ensure_device_jid(self._own_jid), 0)
        self._peer_ssrcs = [generate_secure_ssrc(call_id, _ensure_device_jid(peer_jid), 0)]

        call = CallInfo.new_incoming(call_id, peer_jid, creator)
        call.encryption_key = getattr(offer_entity, "callKey", None)
        self._call = call

        self._init_codec()
        self._rtp_session = RtpSession.whatsapp_opus(self._self_ssrc)
        self._first_packet_sent = False

        # ── Extract relay info FIRST, then init SRTP once with full context ──
        relay_attr = getattr(offer_entity, "relay", None)
        if relay_attr is not None:
            relay_data = relay_attr.to_relay_data()
            # Get rte from the entity (extracted from <offer><rte>)
            rte_bytes = getattr(offer_entity, "rte", None) or b""
            relay_data["rte"] = rte_bytes if isinstance(rte_bytes, bytes) else b""
            self._log.info("Relay parsed from offer: relays=%d participants=%s uuid=%s rte=%s",
                           len(relay_data["relays"]), relay_data["participant_jids"],
                           relay_data["uuid"],
                           relay_data["rte"][:10].hex() if relay_data["rte"] else "none")
            if relay_data["relays"]:
                call.relay_data = relay_data
                # Always refine SSRCs when relay_data is available —
                # self_pid/peer_pid determine the correct SSRC seeds.
                self._refine_ssrcs_from_participants(
                    relay_data.get("participant_jids", []),
                    relay_data.get("participants", []))
                self._init_srtp_keys()

        if self.on_incoming:
            self.on_incoming(self, call)

        self._emit_state()
        self._log.info("Incoming call: %s from %s (relay_eps=%d)",
                       call_id, peer_jid,
                       len(call.relay_data.get("relays", [])) if call.relay_data else 0)

        if call.relay_data and call.encryption_key:
            # Connect to relay IMMEDIATELY (before relaylatency from peer).
            # For outgoing calls, the caller connects first and media works.
            # For incoming, connecting immediately may help us be first.
            self._log.info("Incoming call: connecting to relay immediately (%d eps)",
                           len(call.relay_data.get("relays", [])))
            self._connect_relays(call.relay_data["relays"])
            asyncio.ensure_future(self._auto_accept())
        else:
            self._log.warning("Incoming call: cannot auto-accept — no relay data or callKey")

    # ── Accept / reject / end ──────────────────────────────────

    async def _auto_accept(self):
        # Delay 3s before auto-accepting — enough time for relaylatency
        # exchange but short enough that the peer won't time out (~8s).
        await asyncio.sleep(3)
        try:
            await self.accept_call()
        except CallError as e:
            self._log.info("auto-accept skipped: %s (call likely terminated by caller)", e)
        except Exception as e:
            self._log.error("auto-accept failed: %s", e, exc_info=True)

    async def accept_call(self) -> None:
        """Accept the current incoming call (send accept stanza)."""
        call = self._call
        if not call or not call.can_accept():
            raise CallError("No incoming call to accept")

        self._log.info("accept_call: sending accept, relay_data=%s",
                       "present" if call.relay_data else "MISSING")

        call.apply_transition(Transition.LOCAL_ACCEPTED)
        self._emit_state()

        peer = call.peer_jid
        creator = call.call_creator

        if self._send_node:
            from ..signaling.builder import build_accept_stanza
            try:
                # Generate P2P te candidates (matching real device behavior).
                # Even though we prefer relay, sending te candidates tells the
                # peer we have network connectivity. Real device always sends
                # te candidates in accept regardless of net medium.
                te_candidates = self._generate_te_candidates()
                accept_entity = build_accept_stanza(
                    peer, call.call_id, creator,
                    te_candidates=te_candidates if te_candidates else None,
                )
                await self._send_node(accept_entity)
                self._log.info("accept_call: accept sent (netMedium=2, te_candidates=%d), waiting for transport from caller",
                               len(te_candidates) if te_candidates else 0)
            except Exception as e:
                self._log.error("accept send failed: %s", e)

        if self._send_node:
            from ..signaling.builder import build_mute_v2_stanza
            try:
                mute_node = build_mute_v2_stanza(peer, call.call_id, creator, muted=0)
                asyncio.ensure_future(self._send_node(mute_node))
                self._log.info("accept_call: mute_v2 (unmuted) sent to %s", peer)
            except Exception as e:
                self._log.error("accept_call: mute_v2 send failed: %s", e)

        self._log.info("Call accepted: %s", call.call_id)

        if call.relay_data and call.relay_data.get("relays"):
            rdata = call.relay_data
            # Swap PIDs: offer's self_pid is the caller's PID, peer_pid is ours.
            # As the callee, we need self_pid=offer.peer_pid, peer_pid=offer.self_pid.
            offer_self_pid = rdata.get("self_pid") or 0
            offer_peer_pid = rdata.get("peer_pid") or 0
            self._relay.set_pids(
                offer_peer_pid,  # our PID = caller's peer_pid
                offer_self_pid,  # peer PID = caller's self_pid
            )
            self._relay.set_ssrc(self._self_ssrc)
            self._relay.set_subscription_ssrcs(self._peer_ssrcs)
            if not self._has_relay:
                self._log.info("accept_call: connecting to %d relays (pid self=%d peer=%d)",
                               len(rdata["relays"]),
                               rdata.get("self_pid") or 0,
                               rdata.get("peer_pid") or 0)
                self._connect_relays(rdata["relays"])
            else:
                self._log.info("accept_call: relay already connected, skipping _connect_relays")
                self._relay.resend_subscriptions()

    async def reject_call(self, reason: EndReason = EndReason.DECLINED) -> None:
        call = self._call
        if not call:
            return
        call.apply_transition(Transition.LOCAL_REJECTED, reason)
        self._emit_state()
        self._cleanup_media()
        self._log.info("Call rejected: %s", call.call_id)

    def _generate_te_candidates(self) -> list[dict]:
        """Generate P2P ICE candidates for accept/transport stanzas.

        Each candidate is {"priority": int, "data": bytes} where data is
        6 bytes: 4B IPv4 + 2B port (big-endian).

        priority=96: host (local) candidate
        priority=32: server-reflexive (STUN) candidate

        Generates a host candidate from a local UDP socket.
        The srflx candidate is obtained via STUN binding to a relay server
        (if one is connected) or a public STUN server.
        """
        import socket
        candidates = []
        try:
            # Create a temporary UDP socket to discover local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            local_port = s.getsockname()[1]
            s.close()

            # Pack as 6-byte address: 4B IP + 2B port
            ip_parts = [int(x) for x in local_ip.split(".")]
            addr = bytes(ip_parts) + local_port.to_bytes(2, "big")
            candidates.append({"priority": 96, "data": addr})
            self._log.info("te_candidates: host %s:%d (priority=96)", local_ip, local_port)
        except Exception as e:
            self._log.warning("te_candidates: failed to get host candidate: %s", e)

        # Try to get srflx candidate via STUN binding to a connected relay
        try:
            srflx = self._get_srflx_candidate()
            if srflx:
                candidates.append(srflx)
        except Exception as e:
            self._log.warning("te_candidates: failed to get srflx candidate: %s", e)

        return candidates

    def _get_srflx_candidate(self) -> dict | None:
        """Get server-reflexive candidate via STUN binding to the connected relay.

        Uses the WhatsApp relay (already connected via AllocReq) as a STUN server
        to discover our public IP:port. Falls back to public STUN if needed.
        """
        # First try the connected WhatsApp relay (gives accurate srflx)
        relay_addr = self._relay.get_srflx_address()
        if relay_addr:
            ip, port = relay_addr
            ip_parts = [int(x) for x in ip.split(".")]
            addr = bytes(ip_parts) + port.to_bytes(2, "big")
            self._log.info("te_candidates: srflx %s:%d (priority=32, via WhatsApp relay)", ip, port)
            return {"priority": 32, "data": addr}

        # Fallback: public STUN servers
        import socket
        stun_servers = [
            ("stun.l.google.com", 19302),
            ("stun1.l.google.com", 19302),
            ("stun.cloudflare.com", 3478),
        ]

        from ..transport.stun import build_binding_request, parse_stun_binding_response
        request = build_binding_request(
            username=None,
            hmac_key=None,
            sender_subscriptions=None,
            include_ice_controlling=False,
            include_fingerprint=False,
        )

        for stun_host, stun_port in stun_servers:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(2.0)
                s.sendto(request, (stun_host, stun_port))
                response, _ = s.recvfrom(2048)
                local_addr = s.getsockname()
                s.close()

                result = parse_stun_binding_response(response)
                if result:
                    ip, port = result
                    ip_parts = [int(x) for x in ip.split(".")]
                    addr = bytes(ip_parts) + port.to_bytes(2, "big")
                    self._log.info("te_candidates: srflx %s:%d (priority=32, via %s:%d, local=%s)",
                                   ip, port, stun_host, stun_port, local_addr)
                    return {"priority": 32, "data": addr}
            except socket.timeout:
                self._log.debug("te_candidates: STUN timeout (%s:%d)", stun_host, stun_port)
            except Exception as e:
                self._log.debug("te_candidates: STUN failed (%s:%d): %s", stun_host, stun_port, e)
        return None

    async def end_call(self, reason: EndReason = EndReason.USER_ENDED) -> None:
        call = self._call
        if not call or call.is_ended():
            return

        call.apply_transition(Transition.TERMINATED, reason)
        self._emit_state()

        if self._send_node:
            try:
                from core.layers.protocol_calls.protocolentities.call_terminate import TerminateCallProtocolEntity
                from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes
                meta = CallMetaAttributes(recipient=call.peer_jid)
                term = TerminateCallProtocolEntity(
                    callId=call.call_id,
                    callCreator=call.call_creator,
                    callMetaAttributes=meta,
                )
                await self._send_node(term)
            except Exception as e:
                self._log.debug("terminate send failed: %s", e)

        if self.on_ended:
            self.on_ended(self, call)

        self._cleanup_media()
        self._log.info("Call ended: %s (reason=%s)", call.call_id, reason.value)

    # ── Signaling event handlers ───────────────────────────────

    def handle_call_accept(self, accept_entity) -> None:
        """Handle remote accept of our outgoing call."""
        from .call_manager import _ensure_device_jid

        call = self._call
        peer_jid = accept_entity.getFrom()

        if not call or call.is_ended():
            if call and call.is_ended():
                self._cleanup_media()
            call_id = accept_entity.getCallId()
            creator = accept_entity.getCallCreator() or peer_jid
            call = CallInfo.new_outgoing(call_id, peer_jid, creator)
            call.apply_transition(Transition.OFFER_SENT)
            self._call = call
            self._call_id = call_id
            self._self_ssrc = generate_secure_ssrc(call_id, _ensure_device_jid(self._own_jid), 0)
            self._peer_ssrcs = [generate_secure_ssrc(call_id, _ensure_device_jid(peer_jid), 0)]
            self._init_codec()
            self._rtp_session = RtpSession.whatsapp_opus(self._self_ssrc)
            self._first_packet_sent = False
            self._log.info("Call auto-created from accept: %s", call_id)

        self._init_codec()
        if not self._rtp_session:
            self._rtp_session = RtpSession.whatsapp_opus(self._self_ssrc)

        try:
            call.apply_transition(Transition.REMOTE_ACCEPTED)
        except InvalidTransition:
            pass
        self._accepted_by_jid = accept_entity.getFrom() or call.peer_jid
        self._emit_state()

        if call.encryption_key:
            self._init_srtp_keys()

        transport_peer = accept_entity.getFrom() or call.peer_jid

        rd = call.relay_data or {}
        rte_val = rd.get("rte", b"")
        self._log.warning("handle_call_accept: relay_data keys=%s rte=%s",
                         list(rd.keys()),
                         rte_val[:20].hex() if rte_val else "EMPTY")
        if self._send_node:
            from ..signaling.builder import build_transport_stanza, build_mute_v2_stanza
            rte = call.relay_data.get("rte", "") if call.relay_data else ""

            # Send a single transport (type=1) — matches Go reference
            # (callmanager_signaling.go HandleCallAccept).  No type=4 or
            # per-protocol variants; build_transport_stanza already
            # hardcodes net protocol=0 medium=2.
            transport_node = build_transport_stanza(
                transport_peer, call.call_id, call.call_creator,
                transport_message_type="1",
                relay_endpoints=[],
                rte=rte,
            )
            asyncio.ensure_future(self._send_node(transport_node))
            self._log.info("Sending transport (type=1) to %s", transport_peer)

            try:
                mute_node = build_mute_v2_stanza(
                    transport_peer, call.call_id, call.call_creator, muted=0)
                asyncio.ensure_future(self._send_node(mute_node))
                self._log.info("Sent mute_v2 (unmuted) to %s", transport_peer)
            except Exception as e:
                self._log.error("mute_v2 send failed: %s", e)
        else:
            self._log.warning("Cannot send transport: _send_node is None (bot hooks not registered)")

        self._relay.resend_subscriptions()

        self._log.info("handle_call_accept: has_relay=%s codec_enc=%s codec_dec=%s tx=%s rtp=%s",
                       self._has_relay,
                       self._encode_codec is not None,
                       self._decode_codec is not None,
                       self._tx is not None, self._rtp_session is not None)

        if self._has_relay:
            try:
                call.apply_transition(Transition.MEDIA_CONNECTED)
                self._emit_state()
            except InvalidTransition:
                pass
            self._start_silence_keepalive()

        self._log.info("Remote accepted: %s (relays=%d)",
                       call.call_id,
                       len(call.relay_data.get("relays", [])) if call.relay_data else 0)

    def _send_relaylatency(self):
        call = self._call
        if not call or not self._send_node:
            return
        entries = self._relay.get_relay_entries()
        if not entries:
            self._log.info("_send_relaylatency: no connected relays to report")
            return
        # Only report the best (lowest-latency) relay — matches real device.
        best = min(entries, key=lambda e: e.get("rtt_ms", 0))
        self._log.info("_send_relaylatency: reporting best relay %s (rtt=%dms) to %s",
                       best.get("relay_name", "?"), best.get("rtt_ms", 0), call.peer_jid)
        from ..signaling.builder import build_relaylatency_stanza
        stanza = build_relaylatency_stanza(
            call.peer_jid, call.call_id, call.call_creator, [best],
        )
        asyncio.ensure_future(self._send_node(stanza))

    def handle_relaylatency(self, entity) -> None:
        """Handle relaylatency from peer — we already connected in handle_call_offer."""
        call = self._call
        if not call:
            return
        self._log.info("relaylatency: received from %s (already connected)", call.peer_jid)

    def handle_call_transport(self, transport_entity) -> None:
        call = self._call
        if not call:
            return

        try:
            self._handle_transport_inner(transport_entity)
        except Exception:
            self._log.error("handle_call_transport CRASHED", exc_info=True)

    def _handle_transport_inner(self, transport_entity) -> None:
        call = self._call
        if not call:
            return

        node = getattr(transport_entity, "toProtocolTreeNode", lambda: None)()
        tmt = "0"
        te_candidates = []
        if node:
            transport_node = node.getChild("transport")
            if transport_node:
                attrs = getattr(transport_node, "attributes", {}) or {}
                tmt = attrs.get("transport-message-type", "0")
                # Parse <te> P2P candidates from peer's transport
                for te_node in transport_node.getAllChildren("te"):
                    priority = te_node.getAttributeValue("priority")
                    te_data = te_node.getData()
                    if te_data:
                        import base64
                        try:
                            raw = base64.b64decode(te_data) if isinstance(te_data, str) else te_data
                        except Exception:
                            raw = te_data if isinstance(te_data, bytes) else b""
                        if 6 <= len(raw) <= 18:
                            ip = ".".join(str(b) for b in raw[0:4])
                            port = (raw[4] << 8) | raw[5]
                            te_candidates.append({"priority": int(priority) if priority else 0, "ip": ip, "port": port, "data": raw})

        self._log.info("Transport received: %s (type=%s, te_candidates=%s)",
                       call.call_id, tmt,
                       [(c["ip"], c["port"], c["priority"]) for c in te_candidates])

        # Store peer P2P candidates for potential P2P test
        if te_candidates:
            self._peer_p2p_candidates = te_candidates
            self._log.info("P2P candidates from peer: %s",
                           [(c["ip"], c["port"]) for c in te_candidates])

        if tmt == "1" and call.relay_data and not self._has_relay:
            self._log.info("Transport type=1 → connecting relay (%d eps)",
                          len(call.relay_data.get("relays", [])))
            self._relay.set_ssrc(self._self_ssrc)
            self._relay.set_subscription_ssrcs(self._peer_ssrcs)
            if call.encryption_key:
                self._init_srtp_keys()
            self._connect_relays(call.relay_data.get("relays", []))
        elif tmt == "1" and self._has_relay:
            self._log.info("Transport type=1 received, relay already connected — resending subscriptions")
            self._relay.resend_subscriptions()
            # Reply with our own transport type=1.
            # Include <te> P2P candidates so the peer can reach us directly.
            # Include <rte> ONLY for outgoing calls (we have our rte from ack).
            # For incoming calls: the rte in relay_data is the PEER's rte from
            # the offer — sending it back is wrong. We omit rte.
            if self._send_node:
                from ..signaling.builder import build_transport_stanza
                try:
                    is_outgoing = call.direction == CallDirection.OUTGOING
                    rte = b""
                    if is_outgoing and call.relay_data:
                        rte_raw = call.relay_data.get("rte", b"")
                        rte = rte_raw if isinstance(rte_raw, bytes) else b""
                    # Generate te candidates for transport reply (for P2P)
                    te_cands = self._generate_te_candidates() if self._p2p_enabled else []
                    tp_entity = build_transport_stanza(
                        call.peer_jid, call.call_id, call.call_creator,
                        transport_message_type="1",
                        rte=rte,
                        te_candidates=te_cands if te_cands else None,
                    )
                    asyncio.ensure_future(self._send_node(tp_entity))
                    self._log.info("Transport type=1 reply sent (dir=%s rte=%s te=%d)",
                                   "out" if is_outgoing else "in",
                                   rte[:10].hex() if rte else "none",
                                   len(te_cands) if te_cands else 0)
                except Exception as e:
                    self._log.error("Transport type=1 reply failed: %s", e)

            # ── P2P test: also send audio directly to peer's candidates ──
            if self._p2p_enabled and self._peer_p2p_candidates and not self._p2p_socket:
                self._start_p2p()

        if tmt in ("3", "4") and self._send_node:
            from ..signaling.builder import build_transport_keepalive
            try:
                ka_node = build_transport_keepalive(call.peer_jid, call.call_id, call.call_creator)
                asyncio.ensure_future(self._send_node(ka_node))
                self._log.info("Transport keepalive (type=9) sent in reply to type=%s", tmt)
            except Exception as e:
                self._log.error("Transport keepalive send failed: %s", e)

    def handle_call_terminate(self, terminate_entity) -> None:
        call = self._call
        if not call or call.is_ended():
            return

        term_call_id = getattr(terminate_entity, "getCallId", lambda: "")()
        self._log.info("handle_call_terminate: call_id=%s state=%s direction=%s",
                       term_call_id, call.state.value, call.direction.value)

        call.apply_transition(Transition.TERMINATED, EndReason.USER_ENDED)
        self._emit_state()

        if self.on_ended:
            self.on_ended(self, call)

        self._cleanup_media()

    # ── Audio I/O ──────────────────────────────────────────────

    def feed_audio(self, pcm: list[float]) -> None:
        if self.SILENT_MODE:
            return
        if not self._tx:
            return
        self._last_capture_at = time.time()
        self._tx.feed_pcm(pcm)

    # ── Internal ───────────────────────────────────────────────

    # ── Codec: MLow only (opus_mlow SMPL bitstream incompatible with WhatsApp) ──
    CODEC_MODE = "mlow"

    def _init_codec(self):
        if self._encode_codec and self._decode_codec:
            return

        try:
            c = MLowCodec()
            if c.available:
                self._encode_codec = c
                self._decode_codec = c
                self._log.info("Codec: MLow %dHz (shared enc+dec)", c.sample_rate())
                return
        except Exception:
            self._log.exception("MLowCodec init failed")

        self._encode_codec = NullCodec()
        self._decode_codec = NullCodec()
        self._log.warning("Codec: NullCodec")

    def _on_raw_mlow(self, mlow: bytes):
        self._last_raw_mlow = mlow
        self._raw_cnt += 1
        if self._raw_cnt <= 5:
            self._log.warning("ECHO RAW: stored %dB (cnt=%d, test=%s, captured=%s)",
                              len(mlow), self._raw_cnt, self._echo_test,
                              bool(self._echo_frame))

    def _on_audio_decoded(self, pcm: list[float], rtp_ts: int = 0):
        FRAME_SAMPLES = 960
        self._audio_frame_cnt += 1

        if self._first_rtp_ts is None:
            self._first_rtp_ts = rtp_ts
            self._recv_pcm_pos = 0

        ts_delta = (rtp_ts - self._first_rtp_ts) & 0xFFFFFFFF
        target_pos = ts_delta

        MAX_RECV_PCM = 16000 * 30  # 30 seconds max buffer
        if target_pos > MAX_RECV_PCM:
            # Trim old data instead of resetting entire buffer
            trim = target_pos - MAX_RECV_PCM
            self._recv_pcm = self._recv_pcm[trim:]
            self._first_rtp_ts = (self._first_rtp_ts + trim) & 0xFFFFFFFF
            target_pos = MAX_RECV_PCM

        gap = target_pos - len(self._recv_pcm)
        if gap > 0:
            self._recv_pcm.extend(self._silence_frame * (gap // FRAME_SAMPLES))
            rem = gap % FRAME_SAMPLES
            if rem > 0:
                self._recv_pcm.extend(array('f', [0.0]) * rem)

        need = target_pos + len(pcm)
        if need > len(self._recv_pcm):
            self._recv_pcm.extend(array('f', [0.0]) * (need - len(self._recv_pcm)))
        # Bulk copy via slice assignment (fast C-level)
        pcm_arr = array('f', pcm)
        self._recv_pcm[target_pos:target_pos + len(pcm)] = pcm_arr

        if self._audio_frame_cnt <= 5 or self._audio_frame_cnt % 100 == 0:
            rms = math.sqrt(sum(s*s for s in pcm) / max(len(pcm), 1))
            self._log.info("AUDIO_DECODED #%d: %d samples RMS=%.5f total=%d (%.1fs)",
                           self._audio_frame_cnt, len(pcm), rms,
                           len(self._recv_pcm), len(self._recv_pcm) / 16000.0)
        if self.on_peer_audio:
            self.on_peer_audio(self, pcm)

        if self._echo_test and not self._echo_frame and self._last_raw_mlow:
            rms = math.sqrt(sum(s*s for s in pcm) / max(len(pcm), 1))
            if rms > 0.01:
                self._echo_frame = bytes(self._last_raw_mlow)
                self._log.warning("ECHO TEST: captured peer frame (%dB, rms=%.4f) — replaying on TX",
                                  len(self._echo_frame), rms)
            elif not self._echo_rms_logged:
                self._echo_rms_logged = True
                self._log.warning("ECHO TEST: waiting for speech (rms=%.6f, have_raw=%d)",
                                  rms, len(self._last_raw_mlow))

    def _init_srtp_keys(self, peer_key: bytes = None):
        from .call_manager import _ensure_device_jid, _find_our_device

        def _qualify_lid_srtp(jid: str) -> str:
            if "@lid" in jid and ":" not in jid.split("@")[0]:
                return jid.replace("@lid", ":0@lid")
            return jid

        self._log.info("_init_srtp_keys: tx=%s rx=%s call=%s enc_key_len=%d relay_data=%s",
                       self._tx is not None, self._rx is not None,
                       self._call is not None,
                       len(self._call.encryption_key) if (self._call and self._call.encryption_key) else 0,
                       "present" if (self._call and self._call.relay_data) else "MISSING")
        if self._tx and self._rx:
            has_relay = bool(self._call and self._call.relay_data)
            prev_accepted = self._srtp_accepted_by
            curr_accepted = self._accepted_by_jid
            if (has_relay and not self._had_relay_data) or \
               (curr_accepted and curr_accepted != prev_accepted):
                self._log.info("_init_srtp_keys: re-initializing (relay=%s, accepted_by=%s→%s)",
                               has_relay and not self._had_relay_data,
                               prev_accepted, curr_accepted)
                if self._decode_codec and hasattr(self._decode_codec, 'reset_decoder'):
                    self._decode_codec.reset_decoder()
                if self._encode_codec and hasattr(self._encode_codec, 'reset_encoder'):
                    self._encode_codec.reset_encoder()
                    self._log.info("_init_srtp_keys: MLow decoder+encoder state reset")
            else:
                self._log.warning("_init_srtp_keys: SKIP — already initialized")
                return
        self._had_relay_data = bool(self._call and self._call.relay_data)
        self._srtp_accepted_by = self._accepted_by_jid
        call = self._call
        if not call or not call.encryption_key:
            self._log.warning("_init_srtp_keys: SKIP — no call or no encryption_key")
            return

        ck = call.encryption_key

        # ── Peer JID ──
        # Priority: accepted_by_jid (from accept) > call.peer_jid (from offer.from)
        peer_raw = self._accepted_by_jid or call.peer_jid
        peer_device = _ensure_device_jid(peer_raw)

        # ── Our JID ──
        participants = []
        if call.relay_data:
            participants = call.relay_data.get("participant_jids", []) or []
        our_device = _ensure_device_jid(
            _find_our_device(participants, self._own_jid))

        self._log.info("SRTP JIDs: our=%s peer=%s (accepted_by=%s)",
                       our_device, peer_device,
                       self._accepted_by_jid)

        warp_ak = derive_warp_auth_key(ck)

        send_mat = derive_per_jid_srtp_key(ck, our_device)
        self._srtp_send = SrtpContext(send_mat.master_key, send_mat.master_salt,
                                       warp_auth_key=warp_ak)

        recv_mat = derive_per_jid_srtp_key(peer_key or ck, peer_device)
        self._log.info("SRTP recv: master_key=%s master_salt=%s (from peer LID: %s)",
                       recv_mat.master_key.hex(), recv_mat.master_salt.hex(),
                       peer_device)
        self._srtp_recv = SrtpContext(recv_mat.master_key, recv_mat.master_salt,
                                       warp_auth_key=warp_ak)
        self._log.warning(
            "CRYPTO_INIT: callKey=%s peerLID=%s master_key=%s master_salt=%s "
            "session_key=%s session_salt=%s auth_key=%s warp_auth_key=%s",
            ck.hex(), peer_device,
            recv_mat.master_key.hex(), recv_mat.master_salt.hex(),
            self._srtp_recv.session_key.hex(),
            self._srtp_recv.session_salt.hex(),
            self._srtp_recv.auth_key.hex(),
            warp_ak.hex(),
        )

        if self._encode_codec and self._decode_codec:
            if not self._rtp_session:
                self._rtp_session = RtpSession.whatsapp_opus(self._self_ssrc)
            hbh_ctx = None
            if call.relay_data:
                hbh_key = call.relay_data.get("hbh_key")
                self._log.info("HBH: relay_data keys=%s, hbh_key=%s",
                               list(call.relay_data.keys()),
                               "%dB" % len(hbh_key) if hbh_key else "MISSING")
                if hbh_key and len(hbh_key) == 30:
                    hbh_ctx = SrtpContext(hbh_key[:16], hbh_key[16:30], hbh=True)
                    self._log.info("HBH SRTP context created (hbh=True) key=%s", hbh_key.hex())
                elif hbh_key:
                    self._log.warning("HBH: hbh_key wrong size: %dB (expected 30)", len(hbh_key))
            else:
                self._log.warning("HBH: call.relay_data is None")

            from ..media.sframe import SframeSession
            sframe_ctx = SframeSession(ck, our_device, peer_device)
            self._log.info("SFrame session created: send_key=%s.. recv_key=%s..",
                           sframe_ctx.encrypt_key.hex()[:8],
                           sframe_ctx.decrypt_key.hex()[:8])

            self._tx = TxPipeline(self._encode_codec, self._rtp_session, self._srtp_send, self._relay,
                                  hbh_ctx, sframe_ctx,
                                  p2p_callback=lambda data: self._send_p2p(data))
            peer_ssrc = self._peer_ssrcs[0] if self._peer_ssrcs else 0
            self._rx = RxPipeline(self._decode_codec, self._srtp_recv, sframe_ctx, hbh_ctx, peer_ssrc)
            self._rx.on_audio = self._on_audio_decoded
            self._rx.on_raw_mlow = self._on_raw_mlow
            if self._has_relay and self._call and self._call.state in (CallState.CONNECTING, CallState.ACTIVE):
                self._start_silence_keepalive()

        self._log.info("SRTP keys: call_key_len=%d call_key=%s send_jid=%s send_master=%s recv_jid=%s recv_master=%s",
                       len(ck), ck.hex(),
                       our_device, send_mat.master_key.hex(),
                       peer_device, recv_mat.master_key.hex())



    def _connect_relays(self, endpoints: list):
        from .call_manager import _build_relay_configs, _ensure_device_jid

        # Guard: don't configure relays more than once.
        # configure_relays() creates a new UDP socket and connection list;
        # calling it again would orphan the existing socket and break the
        # already-connected relay.
        if self._has_relay:
            self._log.info("_connect_relays: already connected, skipping")
            return
        if self._relay._connections:
            self._log.info("_connect_relays: already configuring, skipping")
            return

        relays = _build_relay_configs(endpoints)
        if not relays:
            self._log.error("relay: no usable relay configs")
            return

        call = self._call
        if self._self_ssrc == 0 and call:
            self._self_ssrc = generate_secure_ssrc(call.call_id, _ensure_device_jid(self._own_jid), 0)
            self._log.info("SSRC auto-initialized: %d", self._self_ssrc)
        if (not self._peer_ssrcs or self._peer_ssrcs[0] == 0) and call:
            peer_ssrc = generate_secure_ssrc(call.call_id, _ensure_device_jid(call.peer_jid), 0)
            self._peer_ssrcs = [peer_ssrc]
            self._log.info("Peer SSRC auto-initialized: %d", peer_ssrc)

        self._relay.set_ssrc(self._self_ssrc)
        self._relay.set_subscription_ssrcs(self._peer_ssrcs)

        # Pass call info for SSRC matrix derivation
        if call:
            from .call_manager import _ensure_device_jid
            self._relay.set_call_info(
                call.call_id,
                _ensure_device_jid(self._own_jid),
                _ensure_device_jid(call.peer_jid),
            )

        # Only override PIDs if they haven't been set from relay data yet.
        # The parsed relay node includes self_pid/peer_pid and participant PIDs
        # which are needed for correct SSRC matrix derivation.
        if self._relay._self_pid == 0 and self._relay._peer_pid == 0:
            self._relay.set_pids(0, 0)
            self._log.info("Relay PIDs set: self=0 peer=0 (default)")
        else:
            self._log.info("Relay PIDs preserved: self=%d peer=%d",
                           self._relay._self_pid, self._relay._peer_pid)

        asyncio.ensure_future(self._relay.configure_relays(relays))
        self._log.info("relay configured, endpoints=%d", len(relays))

    def _refine_ssrcs_from_participants(self, participants: list[str],
                                         participant_infos=None):
        from .call_manager import (_ensure_device_jid, _find_our_device,
                                   _build_pid_jid_map)

        call = self._call
        if not call:
            return

        def _qualify_lid(jid: str) -> str:
            if "@lid" in jid and ":" not in jid.split("@")[0]:
                return jid.replace("@lid", ":0@lid")
            return jid

        # ── Refine OUR SSRC from the participant that matches our JID ──
        if participants:
            our_device = _find_our_device(participants, self._own_jid)
            if our_device:
                our_device = _qualify_lid(our_device)
                new_self = generate_secure_ssrc(call.call_id, our_device, 0)
                if new_self != self._self_ssrc:
                    self._self_ssrc = new_self
                    self._rtp_session = RtpSession.whatsapp_opus(new_self)
                    self._relay.set_ssrc(new_self)

        # ── Build PID→JID map for SSRC matrix ──
        # Participants (from relay sender) tell us which JID is at each PID.
        # E.g. ack may have pid=0+jid=X and pid=2+jid=Y for multi-device peer.
        if participant_infos:
            pid_jid_map = _build_pid_jid_map(participant_infos)
            if pid_jid_map:
                self._relay.set_pid_jid_map(pid_jid_map)
                self._log.info("PID→JID map: %s", pid_jid_map)

        # ── Peer SSRC: always seed=0 ──
        peer_device = _ensure_device_jid(call.peer_jid)
        if peer_device:
            new_peer = generate_secure_ssrc(call.call_id, peer_device, 0)
            if [new_peer] != self._peer_ssrcs:
                self._peer_ssrcs = [new_peer]
                self._relay.set_subscription_ssrcs([new_peer])
                self._log.info("Refined peer SSRC: 0x%08x (jid=%s)", new_peer, peer_device)

    def _on_relay_connected(self):
        self._peer_ssrc_observed = False
        self._log.info("_on_relay_connected: call=%s ended=%s codec=%s tx=%s rx=%s state=%s",
                       self._call is not None,
                       self._call.is_ended() if self._call else "N/A",
                       self._encode_codec is not None and self._decode_codec is not None,
                       self._tx is not None,
                       self._rx is not None,
                       self._call.state.value if self._call else "N/A")
        if not self._call or self._call.is_ended():
            return
        if self._call.state not in (CallState.CONNECTING, CallState.ACTIVE):
            self._log.info("_on_relay_connected: relay up, initializing RX only — state=%s",
                           self._call.state.value)
            if self._call.encryption_key:
                self._init_srtp_keys()
            self._send_relaylatency()
            # Start sending silence keepalive even before accept — the peer
            # needs to receive our media on the relay to know the path works.
            # Real device does this too (sends media immediately after relay
            # connect, before user accepts).
            if self._tx and self._has_relay:
                self._start_silence_keepalive()
            return
        try:
            self._call.apply_transition(Transition.MEDIA_CONNECTED)
            self._emit_state()
            self._init_srtp_keys()
            self._start_silence_keepalive()
            self._log.info("Call ACTIVE (media connected): %s", self._call.call_id)
            self._send_relaylatency()
        except InvalidTransition:
            pass

    def _on_relay_connect_failed(self):
        self._log.error("_on_relay_connect_failed: all relays unreachable, terminating call")
        if self._call and not self._call.is_ended():
            asyncio.ensure_future(self.end_call(EndReason.TIMEOUT))

    def _on_relay_data(self, data: bytes):
        if self._rx:
            self._raw_pkt_cnt += 1
            if self._raw_pkt_cnt <= 10 or self._raw_pkt_cnt % 100 == 0:
                preview = data[:64].hex()
                self._log.info(
                    "RELAY RAW #%d: len=%d first64=%s",
                    self._raw_pkt_cnt, len(data), preview,
                )

            if len(data) >= 12 and not self._peer_ssrc_observed:
                frame_type = (data[0] << 8) | data[1]
                if frame_type in (0x9078, 0x9079, 0x90F8, 0x90F9):
                    ssrc = (data[8] << 24) | (data[9] << 16) | (data[10] << 8) | data[11]
                    old_ssrc = self._peer_ssrcs[0] if self._peer_ssrcs else 0
                    our_ssrcs_track = {self._self_ssrc}
                    if self._rtp_session:
                        our_ssrcs_track.add(self._rtp_session.ssrc)
                    if ssrc not in our_ssrcs_track and ssrc != old_ssrc:
                        self._log.warning("!!! SSRC UPDATE: actual peer SSRC=0x%08x (was guessing 0x%08x)",
                                       ssrc, old_ssrc)
                        self._peer_ssrcs = [ssrc]
                        self._relay.set_subscription_ssrcs(self._peer_ssrcs)
                        self._relay.resend_subscriptions()
                        self._peer_ssrc_observed = True

            if len(data) >= 12:
                frame_type = (data[0] << 8) | data[1]
                if frame_type in (0x9078, 0x9079, 0x90F8, 0x90F9):
                    pkt_ssrc = (data[8] << 24) | (data[9] << 16) | (data[10] << 8) | data[11]
                    our_ssrcs = {self._self_ssrc}
                    if self._rtp_session:
                        our_ssrcs.add(self._rtp_session.ssrc)
                    if pkt_ssrc in our_ssrcs:
                        self._echo_filtered_cnt += 1
                        if self._echo_filtered_cnt <= 3 or self._echo_filtered_cnt % 100 == 0:
                            self._log.info("ECHO FILTERED #%d: ssrc=0x%08x (our TX echo, dropped)",
                                           self._echo_filtered_cnt, pkt_ssrc)
                        return

            self._rx.handle_packet(data)

    def _start_silence_keepalive(self):
        if self.SILENT_MODE:
            self._log.warning("SILENT_MODE: skipping keepalive (no audio TX)")
            return
        if not self._encode_codec or not self._decode_codec:
            self._log.warning("silence keepalive: no codec"); return
        if not self._tx:
            self._log.warning("silence keepalive: no tx pipeline"); return
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
        self._log.info("silence keepalive: starting (enc=%s dec=%s)",
                       type(self._encode_codec).__name__ if self._encode_codec else "none",
                       type(self._decode_codec).__name__ if self._decode_codec else "none")
        self._keepalive_task = asyncio.ensure_future(self._silence_keepalive_loop())

    async def _silence_keepalive_loop(self):
        FRAME_MS = 0.06
        self._log.info("keepalive LOOP started (60ms interval, test audio)")

        test_pcm = []
        try:
            import pickle, os
            pkl_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "test_audio_pcm.pkl")
            if not os.path.exists(pkl_path):
                pkl_path = "test_audio_pcm.pkl"
            with open(pkl_path, "rb") as f:
                test_pcm = pickle.load(f)
            self._log.info("keepalive: loaded %s (%d samples, %.1fs)",
                           pkl_path, len(test_pcm), len(test_pcm) / 16000.0)
        except Exception as e:
            self._log.warning("keepalive: no test audio (%s), falling back to SID frames", e)

        count = 0
        audio_pos = 0
        next_send_time = time.time() + FRAME_MS
        while True:
            try:
                now = time.time()
                sleep_dur = next_send_time - now
                if sleep_dur > 0:
                    await asyncio.sleep(sleep_dur)
                next_send_time = max(next_send_time + FRAME_MS, time.time() + FRAME_MS)

                count += 1
                if not self._tx or not self._has_relay:
                    self._log.warning("keepalive LOOP exiting: tx=%s relay=%s",
                                    self._tx is not None, self._has_relay)
                    break
                if self._call and self._call.is_ended():
                    self._log.info("keepalive LOOP: call ended")
                    break
                idle = time.time() - self._last_capture_at > 0.12
                if idle:
                    if test_pcm:
                        chunk = test_pcm[audio_pos:audio_pos + 960]
                        if len(chunk) < 960:
                            audio_pos = 0
                            chunk = test_pcm[audio_pos:audio_pos + 960]
                        audio_pos += 960
                        self._tx.feed_pcm(chunk)
                        if count <= 3 or count % 200 == 0:
                            self._log.info("keepalive TX #%d (test audio pos=%d/%d)",
                                          count, audio_pos, len(test_pcm))
                    else:
                        self._silence_cnt += 1
                        if self._silence_cnt <= 3:
                            self._log.info("SILENCE_FRAME #%d", self._silence_cnt)
                        self._tx.send_silence_frame()
                        if count <= 3 or count % 100 == 0:
                            self._log.info("keepalive TX #%d (SID)", count)
            except Exception as e:
                self._log.error("keepalive LOOP error: %s", e, exc_info=True)

    # ── P2P direct UDP (test path) ─────────────────────────────

    def _start_p2p(self):
        """Start P2P UDP send/receive to peer's candidates as a test path.

        Creates a UDP socket and begins sending audio directly to the peer's
        P2P addresses (in parallel with relay). Also listens for incoming
        P2P audio from the peer.
        """
        if not self._peer_p2p_candidates:
            self._log.warning("P2P: no peer candidates, skipping")
            return

        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)
            sock.bind(("0.0.0.0", 0))
            local_addr = sock.getsockname()
            self._p2p_socket = sock
            self._log.warning("P2P STARTED: local=%s:%d → peers=%s",
                             local_addr[0], local_addr[1],
                             [(c["ip"], c["port"]) for c in self._peer_p2p_candidates])

            # Start P2P receive loop
            asyncio.get_event_loop().add_reader(sock, self._on_p2p_readable)

            # Send initial test packet to each candidate (just a ping to open NAT)
            ping = b"\x00" * 12  # minimal RTP-like header
            for c in self._peer_p2p_candidates:
                try:
                    sock.sendto(ping, (c["ip"], c["port"]))
                    self._log.info("P2P: ping sent to %s:%d", c["ip"], c["port"])
                except Exception as e:
                    self._log.warning("P2P: ping failed to %s:%d: %s", c["ip"], c["port"], e)
        except Exception as e:
            self._log.error("P2P: failed to start: %s", e)

    def _on_p2p_readable(self):
        """Handle incoming P2P UDP data."""
        if not self._p2p_socket:
            return
        try:
            data, addr = self._p2p_socket.recvfrom(4096)
            if len(data) < 12:
                return
            self._log.warning("P2P RECV: len=%d from %s:%d first16=%s",
                             len(data), addr[0], addr[1], data[:16].hex())
            # Feed P2P audio into the same RxPipeline as relay audio
            if self._rx:
                self._rx.handle_packet(data)
        except BlockingIOError:
            pass
        except Exception as e:
            self._log.error("P2P recv error: %s", e)

    def _send_p2p(self, data: bytes):
        """Send audio data to all peer P2P candidates."""
        if not self._p2p_socket or not self._peer_p2p_candidates:
            return
        for c in self._peer_p2p_candidates:
            try:
                self._p2p_socket.sendto(data, (c["ip"], c["port"]))
            except Exception:
                pass

    def _stop_p2p(self):
        """Stop P2P socket."""
        if self._p2p_socket:
            try:
                loop = asyncio.get_event_loop()
                loop.remove_reader(self._p2p_socket)
            except Exception:
                pass
            try:
                self._p2p_socket.close()
            except Exception:
                pass
            self._p2p_socket = None
            self._log.info("P2P stopped")

    def _cleanup_media(self):
        """Clean up all media resources."""
        if len(self._recv_pcm) > 0:
            self._write_wav()

        self._stop_p2p()

        if self._keepalive_task:
            self._keepalive_task.cancel()
            self._keepalive_task = None

        # Close codecs (avoid double-close if encode==decode)
        for c in {self._encode_codec, self._decode_codec}:
            if c:
                try:
                    c.close()
                except Exception:
                    pass
        self._encode_codec = None
        self._decode_codec = None

        self._tx = None
        self._rx = None
        self._srtp_send = None
        self._srtp_recv = None
        self._rtp_session = None

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._relay.close())
        except RuntimeError:
            pass

        self._first_packet_sent = False
        self._recv_pcm = array('f')
        self._had_relay_data = False
        self._accepted_by_jid = ""
        self._srtp_accepted_by = ""

        # Reset all diagnostic counters
        self._audio_frame_cnt = 0
        self._first_rtp_ts = None
        self._recv_pcm_pos = 0
        self._silence_frame = [0.0] * 960
        self._raw_cnt = 0
        self._raw_pkt_cnt = 0
        self._echo_filtered_cnt = 0
        self._nonstun_cnt = 0
        self._bc_cnt = 0
        self._silence_cnt = 0
        self._peer_ssrc_observed = False
        self._first_packet_log = True
        self._first_packet_sent = False
        self._echo_frame = b""
        self._last_raw_mlow = b""
        self._echo_rms_logged = False
        if self._mlow_dump:
            try:
                self._mlow_dump.close()
            except Exception:
                pass
            self._mlow_dump = None
            self._mlow_dump_count = 0

    def _write_wav(self):
        import struct, time, os
        samples = self._recv_pcm  # array('f')
        sample_rate = 16000
        MAX_WAV_SAMPLES = 16000 * 3600
        if len(samples) > MAX_WAV_SAMPLES:
            self._log.warning("_write_wav: truncating %d samples to %d",
                              len(samples), MAX_WAV_SAMPLES)
            samples = samples[-MAX_WAV_SAMPLES:]
        if len(samples) == 0:
            return
        filename = os.path.join("logs", f"recv_{int(time.time())}.wav")
        os.makedirs("logs", exist_ok=True)
        # array('f') → array('h') bulk convert → bytes (no per-sample struct unpack)
        int16s = array('h', (max(-32768, min(32767, int(s * 32767))) for s in samples))
        data = int16s.tobytes()
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF", 36 + len(data), b"WAVE",
            b"fmt ", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16,
            b"data", len(data),
        )
        with open(filename, "wb") as f:
            f.write(header + data)
        self._log.info("WAV written: %s (%.1fs, %d samples)", filename,
                       len(samples) / sample_rate, len(samples))

    def _emit_state(self):
        if self.on_state_change and self._call:
            self.on_state_change(self, self._call)

    async def close(self):
        if self._call and not self._call.is_ended():
            await self.end_call()
        self._cleanup_media()