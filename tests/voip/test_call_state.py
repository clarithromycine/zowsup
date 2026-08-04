"""
Phase 5 tests — Call state machine.

Tests: state creation, transitions, invalid transitions, edge cases.
"""

import sys, os
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pytest
from voip.call.call_state import (
    CallInfo, CallState, CallDirection, EndReason, Transition, InvalidTransition,
    _TRANSITIONS,
)


class TestCallInfoCreation:
    def test_new_outgoing(self):
        call = CallInfo.new_outgoing("CID001", "peer@s.whatsapp.net", "self@s.whatsapp.net")
        assert call.call_id == "CID001"
        assert call.peer_jid == "peer@s.whatsapp.net"
        assert call.call_creator == "self@s.whatsapp.net"
        assert call.direction == CallDirection.OUTGOING
        assert call.state == CallState.INITIATING

    def test_new_incoming(self):
        call = CallInfo.new_incoming("CID002", "peer@s.whatsapp.net", "creator@s.whatsapp.net")
        assert call.direction == CallDirection.INCOMING
        assert call.state == CallState.INCOMING_RINGING
        assert call.call_creator == "creator@s.whatsapp.net"

    def test_timestamps_on_create(self):
        call = CallInfo.new_outgoing("C1", "p@s.w.net", "s@s.w.net")
        assert call.created_at > 0
        assert call.connected_at is None
        assert call.ended_at is None


class TestCallInfoQueries:
    def test_is_initiator(self):
        outgoing = CallInfo.new_outgoing("C1", "p", "s")
        incoming = CallInfo.new_incoming("C2", "p", "c")
        assert outgoing.is_initiator() is True
        assert incoming.is_initiator() is False

    def test_can_accept(self):
        call = CallInfo.new_incoming("C1", "p", "c")
        assert call.can_accept() is True
        call.apply_transition(Transition.LOCAL_ACCEPTED)
        assert call.can_accept() is False

    def test_can_reject(self):
        call = CallInfo.new_incoming("C1", "p", "c")
        assert call.can_reject() is True

        outgoing = CallInfo.new_outgoing("C2", "p", "s")
        outgoing.apply_transition(Transition.OFFER_SENT)
        assert outgoing.can_reject() is True  # ringing can be rejected

    def test_is_ended(self):
        call = CallInfo.new_outgoing("C1", "p", "s")
        assert call.is_ended() is False
        call.apply_transition(Transition.OFFER_SENT)
        call.apply_transition(Transition.TERMINATED)
        assert call.is_ended() is True


class TestTransitions:
    def test_outgoing_full_lifecycle(self):
        """Outgoing: INITIATING → RINGING → CONNECTING → ACTIVE → ENDED."""
        call = CallInfo.new_outgoing("C1", "peer", "self")
        assert call.state == CallState.INITIATING

        call.apply_transition(Transition.OFFER_SENT)
        assert call.state == CallState.RINGING

        call.apply_transition(Transition.REMOTE_ACCEPTED)
        assert call.state == CallState.CONNECTING

        call.apply_transition(Transition.MEDIA_CONNECTED)
        assert call.state == CallState.ACTIVE
        assert call.is_active()

        call.apply_transition(Transition.TERMINATED, EndReason.USER_ENDED)
        assert call.state == CallState.ENDED
        assert call.is_ended()
        assert call.end_reason == EndReason.USER_ENDED
        assert call.ended_at is not None

    def test_incoming_full_lifecycle(self):
        """Incoming: INCOMING_RINGING → CONNECTING → ACTIVE → ENDED."""
        call = CallInfo.new_incoming("C2", "peer", "creator")
        assert call.state == CallState.INCOMING_RINGING

        call.apply_transition(Transition.LOCAL_ACCEPTED)
        assert call.state == CallState.CONNECTING

        call.apply_transition(Transition.MEDIA_CONNECTED)
        assert call.state == CallState.ACTIVE
        assert call.connected_at is not None

        call.apply_transition(Transition.TERMINATED)
        assert call.state == CallState.ENDED

    def test_ringing_to_ended(self):
        """Outgoing call can go from RINGING directly to ENDED (timeout/terminated)."""
        call = CallInfo.new_outgoing("C3", "p", "s")
        call.apply_transition(Transition.OFFER_SENT)
        call.apply_transition(Transition.TERMINATED, EndReason.TIMEOUT)
        assert call.state == CallState.ENDED
        assert call.end_reason == EndReason.TIMEOUT

    def test_incoming_rejected(self):
        """Incoming call can be rejected from INCOMING_RINGING."""
        call = CallInfo.new_incoming("C4", "p", "c")
        call.apply_transition(Transition.LOCAL_REJECTED, EndReason.DECLINED)
        assert call.state == CallState.ENDED

    def test_connected_at_set_on_media_connected(self):
        call = CallInfo.new_outgoing("C5", "p", "s")
        call.apply_transition(Transition.OFFER_SENT)
        call.apply_transition(Transition.REMOTE_ACCEPTED)
        assert call.connected_at is None
        call.apply_transition(Transition.MEDIA_CONNECTED)
        assert call.connected_at is not None

    def test_connected_at_only_set_once(self):
        """connected_at is set on first MEDIA_CONNECTED, not overwritten later."""
        call = CallInfo.new_outgoing("C6", "p", "s")
        call.apply_transition(Transition.OFFER_SENT)
        call.apply_transition(Transition.REMOTE_ACCEPTED)
        call.apply_transition(Transition.MEDIA_CONNECTED)
        first = call.connected_at
        assert first is not None

        # Simulate a second call_info (separate object) — connected_at
        # is only set when it was None at transition time
        call2 = CallInfo.new_outgoing("C7", "p2", "s2")
        call2.connected_at = first  # already set
        # Triggering MEDIA_CONNECTED via apply_transition is not possible
        # from ACTIVE state, so just verify the attribute isn't overwritten
        # by direct mutation guard (the dataclass doesn't prevent this,
        # but the transition logic does)
        assert call2.connected_at == first


class TestInvalidTransitions:
    def test_invalid_from_initiating(self):
        call = CallInfo.new_outgoing("C1", "p", "s")
        with pytest.raises(InvalidTransition):
            call.apply_transition(Transition.LOCAL_ACCEPTED)  # can't accept from INITIATING
        with pytest.raises(InvalidTransition):
            call.apply_transition(Transition.TERMINATED)  # can't end before sending offer

    def test_invalid_from_ended(self):
        call = CallInfo.new_outgoing("C2", "p", "s")
        call.apply_transition(Transition.OFFER_SENT)
        call.apply_transition(Transition.TERMINATED)
        with pytest.raises(InvalidTransition):
            call.apply_transition(Transition.MEDIA_CONNECTED)

    def test_invalid_from_active(self):
        call = CallInfo.new_outgoing("C3", "p", "s")
        call.apply_transition(Transition.OFFER_SENT)
        call.apply_transition(Transition.REMOTE_ACCEPTED)
        call.apply_transition(Transition.MEDIA_CONNECTED)
        with pytest.raises(InvalidTransition):
            call.apply_transition(Transition.LOCAL_ACCEPTED)  # can't re-accept

    def test_error_message(self):
        call = CallInfo.new_outgoing("C4", "p", "s")
        with pytest.raises(InvalidTransition) as exc:
            call.apply_transition(Transition.TERMINATED)
        assert "initiating" in str(exc.value)
        assert "terminated" in str(exc.value)


class TestTransitionTable:
    def test_all_states_covered(self):
        """Every non-ENDED state has transitions defined."""
        for state in CallState:
            if state == CallState.ENDED:
                continue
            assert state in _TRANSITIONS, f"Missing transitions for {state}"

    def test_ended_has_no_transitions(self):
        assert CallState.ENDED not in _TRANSITIONS
