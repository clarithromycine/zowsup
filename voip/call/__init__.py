"""
VoIP call layer — CallManager, call state machine, call lifecycle.
"""

from .call_state import CallInfo, CallState, CallDirection, EndReason, Transition, InvalidTransition
from .call_manager import CallManager, CallError
