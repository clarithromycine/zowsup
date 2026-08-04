"""
VoIP Call state machine — call lifecycle states and transitions.

Call states: INITIATING → RINGING → CONNECTING → ACTIVE → ENDED
Incoming path:  (offer received) → INCOMING_RINGING → CONNECTING → ACTIVE → ENDED

Reference: WaCalls internal/voip/call/callstate.go
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
import time


class CallState(Enum):
    INITIATING = "initiating"
    RINGING = "ringing"
    INCOMING_RINGING = "incoming_ringing"
    CONNECTING = "connecting"
    ACTIVE = "active"
    ENDED = "ended"


class CallDirection(Enum):
    OUTGOING = "outgoing"
    INCOMING = "incoming"


class EndReason(Enum):
    USER_ENDED = "user_ended"
    DECLINED = "declined"
    TIMEOUT = "timeout"
    BUSY = "busy"
    CANCELLED = "cancelled"
    FAILED = "failed"


# ── Transition names ──────────────────────────────────────────

class Transition:
    OFFER_SENT = "offer_sent"
    OFFER_RECEIVED = "offer_received"
    LOCAL_ACCEPTED = "local_accepted"
    REMOTE_ACCEPTED = "remote_accepted"
    LOCAL_REJECTED = "local_rejected"
    REMOTE_REJECTED = "remote_rejected"
    MEDIA_CONNECTED = "media_connected"
    TERMINATED = "terminated"


# ── Transition table ──────────────────────────────────────────

_TRANSITIONS: dict[CallState, dict[str, CallState]] = {
    CallState.INITIATING: {
        Transition.OFFER_SENT: CallState.RINGING,
        Transition.OFFER_RECEIVED: CallState.INCOMING_RINGING,
    },
    CallState.RINGING: {
        Transition.REMOTE_ACCEPTED: CallState.CONNECTING,
        Transition.MEDIA_CONNECTED: CallState.ACTIVE,
        Transition.TERMINATED: CallState.ENDED,
        Transition.REMOTE_REJECTED: CallState.ENDED,
    },
    CallState.INCOMING_RINGING: {
        Transition.LOCAL_ACCEPTED: CallState.CONNECTING,
        Transition.MEDIA_CONNECTED: CallState.ACTIVE,
        Transition.LOCAL_REJECTED: CallState.ENDED,
        Transition.TERMINATED: CallState.ENDED,
    },
    CallState.CONNECTING: {
        Transition.MEDIA_CONNECTED: CallState.ACTIVE,
        Transition.TERMINATED: CallState.ENDED,
    },
    CallState.ACTIVE: {
        Transition.TERMINATED: CallState.ENDED,
    },
}


class InvalidTransition(Exception):
    def __init__(self, current: str, attempted: str):
        super().__init__(f"Invalid transition '{attempted}' in state '{current}'")


# ── Call info ─────────────────────────────────────────────────


@dataclass
class CallInfo:
    """Immutable call identity + mutable state data (via _state)."""

    call_id: str
    peer_jid: str
    call_creator: str
    direction: CallDirection
    state: CallState = CallState.INITIATING
    encryption_key: Optional[bytes] = None
    relay_data: Optional[dict] = None       # ParsedRelayAck-like dict
    created_at: float = field(default_factory=time.time)
    connected_at: Optional[float] = None
    ended_at: Optional[float] = None
    end_reason: Optional[EndReason] = None

    # ── State queries ──────────────────────────────────────────

    def is_initiator(self) -> bool:
        return self.direction == CallDirection.OUTGOING

    def is_active(self) -> bool:
        return self.state == CallState.ACTIVE

    def is_ringing(self) -> bool:
        return self.state in (CallState.RINGING, CallState.INCOMING_RINGING)

    def is_ended(self) -> bool:
        return self.state == CallState.ENDED

    def can_accept(self) -> bool:
        return self.state == CallState.INCOMING_RINGING

    def can_reject(self) -> bool:
        return self.state in (CallState.INCOMING_RINGING, CallState.RINGING)

    # ── Transitions ────────────────────────────────────────────

    def apply_transition(self, transition: str, reason: EndReason = None) -> None:
        """Apply a state transition. Raises InvalidTransition if not allowed."""
        allowed = _TRANSITIONS.get(self.state, {})
        if transition not in allowed:
            raise InvalidTransition(self.state.value, transition)

        self.state = allowed[transition]

        if transition == Transition.MEDIA_CONNECTED and self.connected_at is None:
            self.connected_at = time.time()

        if transition in (Transition.TERMINATED, Transition.LOCAL_REJECTED, Transition.REMOTE_REJECTED):
            self.ended_at = time.time()
            self.end_reason = reason or EndReason.USER_ENDED

    # ── Factory methods ────────────────────────────────────────

    @classmethod
    def new_outgoing(cls, call_id: str, peer_jid: str, creator_jid: str) -> "CallInfo":
        return cls(
            call_id=call_id,
            peer_jid=peer_jid,
            call_creator=creator_jid,
            direction=CallDirection.OUTGOING,
            state=CallState.INITIATING,
        )

    @classmethod
    def new_incoming(cls, call_id: str, peer_jid: str, call_creator: str) -> "CallInfo":
        return cls(
            call_id=call_id,
            peer_jid=peer_jid,
            call_creator=call_creator,
            direction=CallDirection.INCOMING,
            state=CallState.INCOMING_RINGING,
        )
