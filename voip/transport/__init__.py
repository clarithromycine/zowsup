"""
VoIP transport layer — SCTP relay connection, STUN messaging, subscriptions.

Exports:
- RelayConfig, RelayConnection, RelayManager
- STUN message builders
- Subscription protobuf encoding
"""

from .relay import RelayConfig, RelayManager
from .stun import (
    build_binding_request,
    build_allocate_request,
    build_whatsapp_ping,
    build_sender_subscriptions,
    build_ssrc_subscription_list,
    WASM_STREAM_DESCRIPTORS_TEMPLATE,
    is_stun_packet,
    is_rtp_packet,
)
