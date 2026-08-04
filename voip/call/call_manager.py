

import asyncio
import logging
import random
import string
from typing import Optional, Callable

from .call_state import (
    CallInfo, CallState, CallDirection, EndReason, Transition, InvalidTransition,
)
from .call_session import CallSession, CallError
from ..transport.relay import RelayConfig

log = logging.getLogger(__name__)


class CallManager:
    """
    Multi-call router — dispatches signaling entities to CallSession by call_id.

    CallManager itself holds NO per-call state. All media/relay/SRTP state
    lives in CallSession instances, keyed by call_id in _sessions.
    """

    def __init__(self, bot:None, logger: logging.Logger = None):
        self._log = logger or log

        # ── Sessions: call_id → CallSession ──
        self._sessions: dict[str, CallSession] = {}

        # ── Bot context (shared across all sessions) ──        
        self._bot = bot

        # ── Callbacks (set by VoipAdapter) ──
        # Each callback receives (session, call_info) so the adapter can
        # distinguish which call the event belongs to.
        self.on_state_change: Optional[Callable[[CallSession, CallInfo], None]] = None
        self.on_incoming: Optional[Callable[[CallSession, CallInfo], None]] = None
        self.on_ended: Optional[Callable[[CallSession, CallInfo], None]] = None
        self.on_peer_audio: Optional[Callable[[CallSession, list[float]], None]] = None

    # ── Public API ─────────────────────────────────────────────

    @property
    def current_call(self) -> Optional[CallInfo]:
        """Return the most recently active call (compatibility property)."""
        active = [s for s in self._sessions.values() if s.is_active()]
        if active:
            return active[-1].call
        if self._sessions:
            last = list(self._sessions.values())[-1]
            return last.call
        return None

    def get_call(self, call_id: str) -> Optional[CallInfo]:
        """Get CallInfo for a specific call_id."""
        session = self._sessions.get(call_id)
        return session.call if session else None

    def get_session(self, call_id: str) -> Optional[CallSession]:
        """Get CallSession for a specific call_id."""
        return self._sessions.get(call_id)

    @property
    def active_call_ids(self) -> list[str]:
        """Return list of active (non-ended) call_ids."""
        return [cid for cid, s in self._sessions.items() if s.is_active()]

    # ── Outgoing call ──────────────────────────────────────────

    async def start_call(self, peer_jid: str, is_video: bool = False) -> str:
        """Initiate an outgoing call. Returns the call_id."""
        session = self._create_session(_generate_call_id())        
        self._wire_session_callbacks(session)
        call_id = await session.start_call(peer_jid, is_video)
        self._sessions[call_id] = session
        return call_id

    # ── Accept / reject / end ──────────────────────────────────

    async def accept_call(self, call_id: str = None) -> None:
        """Accept an incoming call by call_id."""
        session = self._find_session(call_id)
        if not session:
            raise CallError("No incoming call to accept")
        await session.accept_call()

    async def reject_call(self, call_id: str = None,
                          reason: EndReason = EndReason.DECLINED) -> None:
        session = self._find_session(call_id)
        if session:
            await session.reject_call(reason)

    async def end_call(self, call_id: str = None,
                      reason: EndReason = EndReason.USER_ENDED) -> None:
        """End a call by call_id. If call_id is None, end the most recent active call."""
        session = self._find_session(call_id)
        if session:
            await session.end_call(reason)

    # ── Signaling entity routing ──────────────────────────────

    def on_call_entity(self, entity) -> None:
        """Route a call protocol entity to the correct CallSession by call_id."""
        call_type = entity.getType()
        call_id = entity.getCallId()

        if call_type == "offer":
            # Incoming offer → create new session
            existing = self._sessions.get(call_id)
            if existing and existing.is_active():
                self._log.info("Duplicate offer for active call %s — ignoring", call_id)
                return
            session = self._create_session(call_id)
            self._wire_session_callbacks(session)
            self._sessions[call_id] = session
            session.handle_call_offer(entity)
        else:
            # Route to existing session by call_id
            session = self._sessions.get(call_id)
            if not session:
                # For accept: may auto-create if call was started outside CallManager
                if call_type == "accept":
                    session = self._create_session(call_id)
                    self._wire_session_callbacks(session)
                    self._sessions[call_id] = session
                    session.handle_call_accept(entity)
                else:
                    self._log.debug("No session for call_id=%s type=%s — ignoring",
                                   call_id, call_type)
                return

            if call_type == "accept":
                session.handle_call_accept(entity)
            elif call_type == "transport":
                session.handle_call_transport(entity)
            elif call_type == "relaylatency":
                session.handle_relaylatency(entity)
            elif call_type == "terminate":
                session.handle_call_terminate(entity)
                if not session.is_active():
                    self._remove_session(call_id)
            elif call_type == "preaccept":
                self._log.debug("preaccept received for call %s", call_id)

    # ── Audio I/O ──────────────────────────────────────────────

    def feed_audio(self, call_id: str, pcm: list[float]) -> None:
        """Feed PCM audio to a specific call's TX pipeline."""
        session = self._sessions.get(call_id)
        if session:
            session.feed_audio(pcm)

    # ── Session management ────────────────────────────────────

    def _create_session(self, call_id: str) -> CallSession:
        """Create a new CallSession with shared bot context."""
        return CallSession(
            call_id=call_id,
            bot=self._bot,
            logger=self._log,
        )

    def _wire_session_callbacks(self, session: CallSession):
        """Wire CallManager-level callbacks to a session."""
        session.on_state_change = self._on_session_state_change
        session.on_incoming = self._on_session_incoming
        session.on_ended = self._on_session_ended
        session.on_peer_audio = self._on_session_peer_audio

    def _find_session(self, call_id: str = None) -> Optional[CallSession]:
        """Find a session by call_id. If None, return the most recent active one."""
        if call_id:
            return self._sessions.get(call_id)
        active = [s for s in self._sessions.values() if s.is_active()]
        if active:
            return active[-1]
        return None

    def _remove_session(self, call_id: str):
        """Remove an ended session from the registry."""
        session = self._sessions.pop(call_id, None)
        if session:
            self._log.info("Session removed: %s (remaining: %d)", call_id, len(self._sessions))

    # ── Session callback wrappers ─────────────────────────────

    def _on_session_state_change(self, session: CallSession, info: CallInfo):
        if self.on_state_change:
            self.on_state_change(session, info)

    def _on_session_incoming(self, session: CallSession, info: CallInfo):
        if self.on_incoming:
            self.on_incoming(session, info)

    def _on_session_ended(self, session: CallSession, info: CallInfo):
        if self.on_ended:
            self.on_ended(session, info)
        self._remove_session(session.call_id)

    def _on_session_peer_audio(self, session: CallSession, pcm: list[float]):
        if self.on_peer_audio:
            self.on_peer_audio(session, pcm)

    # ── Lifecycle ──────────────────────────────────────────────

    async def close(self):
        """End all sessions and cleanup."""
        for session in list(self._sessions.values()):
            try:
                await session.close()
            except Exception:
                pass
        self._sessions.clear()


# ── Helpers (shared with CallSession) ───────────────────────────


def _generate_call_id() -> str:
    """Generate a WhatsApp-style call ID."""
    return "00" + ''.join(random.choices(string.hexdigits.upper(), k=30))


def _build_relay_configs(endpoints: list) -> list:
    """Build RelayConfig list from endpoints. Matches Go buildRelayConfigs() exactly."""
    seen: set[str] = set()
    configs = []
    for ep in endpoints:
        if getattr(ep, "protocol", 0) != 0:
            continue
        if not getattr(ep, "key", "") or not getattr(ep, "raw_token", None):
            continue
        ip = getattr(ep, "ip", "")
        if ip in seen:
            continue
        seen.add(ip)
        relay_name = getattr(ep, "relay_name", "") or ip
        c2r_rtt = getattr(ep, "c2r_rtt", None)
        configs.append(RelayConfig(
            ip=ip,
            port=3478,
            token=getattr(ep, "token", ""),
            auth_token=getattr(ep, "auth_token", ""),
            raw_token=getattr(ep, "raw_token", b""),
            raw_auth_token=getattr(ep, "raw_auth_token", b""),
            key=getattr(ep, "key", ""),
            relay_id=getattr(ep, "relay_id", 0),
            relay_name=relay_name,
            auth_token_id=getattr(ep, "auth_token_id", ""),
            c2r_rtt=c2r_rtt,
        ))
        log.info("VoIP relay cfg: ip=%s name=%s rtt=%s token=%s... key=%s",
                  ip, relay_name, c2r_rtt,
                  getattr(ep, "token", "")[:20],
                  getattr(ep, "key", "")[:20])
    return configs


def _clean_jid(jid: str) -> str:
    """Strip device suffix. '34197200736283:0@lid' → '34197200736283@lid'."""
    colon = jid.find(":")
    if colon >= 0:
        at_pos = jid.find("@")
        if at_pos > colon:
            return jid[:colon] + jid[at_pos:]
    return jid


def _find_our_device(participants: list[str], own_jid: str) -> str:
    """Find our device JID in the participant list."""
    our_base = _clean_jid(own_jid)
    for p in participants:
        if _clean_jid(p) == our_base and ":" in p:
            return p
    return own_jid


def _find_peer_device(participants: list[str], own_jid: str) -> str:
    """Find the peer's primary device JID."""
    our_base = _clean_jid(own_jid)
    for p in participants:
        if _clean_jid(p) != our_base:
            return p
    return ""


def _build_pid_jid_map(participants) -> dict:
    """Build a pid→jid mapping from participant list.

    Accepts list[ParticipantInfo] (from signaling parser) or list[dict]
    (from relay_data). Returns {pid: qualified_jid}.
    """
    result = {}
    for p in participants:
        pid = getattr(p, "pid", 0) if hasattr(p, "pid") else p.get("pid", 0)
        jid = getattr(p, "jid", "") if hasattr(p, "jid") else p.get("jid", "")
        if jid:
            result[pid] = _ensure_device_jid(jid)
    return result


def _ensure_device_jid(jid: str) -> str:
    """Ensure JID has a device suffix (e.g. :0)."""
    if ":" in jid:
        at_pos = jid.find("@")
        colon_pos = jid.find(":")
        if at_pos > colon_pos:
            return jid
    return jid.replace("@", ":0@", 1)


def _relay_endpoint_to_config(ep) -> RelayConfig:
    """Convert a RelayEndpoint (or dict) to RelayConfig."""
    if isinstance(ep, dict):
        return RelayConfig(
            ip=ep.get("ip", ""),
            port=ep.get("port", 3478),
            token=ep.get("token", ""),
            auth_token=ep.get("auth_token", ""),
            raw_token=ep.get("raw_token", b""),
            raw_auth_token=ep.get("raw_auth_token", b""),
            key=ep.get("key", ""),
            relay_id=ep.get("relay_id", 0),
            relay_name=ep.get("relay_name", ""),
            auth_token_id=ep.get("auth_token_id", ""),
            c2r_rtt=ep.get("c2r_rtt"),
        )
    return RelayConfig(
        ip=getattr(ep, "ip", ""),
        port=getattr(ep, "port", 3478),
        token=getattr(ep, "token", ""),
        auth_token=getattr(ep, "auth_token", ""),
        raw_token=getattr(ep, "raw_token", b""),
        raw_auth_token=getattr(ep, "raw_auth_token", b""),
        key=getattr(ep, "key", ""),
        relay_id=getattr(ep, "relay_id", 0),
        relay_name=getattr(ep, "relay_name", ""),
        auth_token_id=getattr(ep, "auth_token_id", ""),
        c2r_rtt=getattr(ep, "c2r_rtt", None),
    )


def _parse_te_relay_endpoints(node) -> list:
    """Parse <te> binary address nodes from an accept/offer stanza."""
    from ..signaling import RelayEndpoint

    relays = []
    for te_node in node.getAllChildren("te"):
        data = te_node.getData()
        if not data or len(data) < 6:
            continue

        ip = ".".join(str(b) for b in data[0:4])
        port = (data[4] << 8) | data[5]
        priority = te_node.getAttributeValue("priority") or "0"

        ep = RelayEndpoint(
            ip=ip,
            port=port,
            relay_name=f"te-candidate-p{priority}",
        )
        relays.append(ep)

    return relays
