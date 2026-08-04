"""
VoIP signaling data classes and parsers.

Data classes define the pure-data interchange format between zowsup core
and the voip module. Parsers extract structured data from WhatsApp XML
(call stanza and relay ack).
"""

from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class RelayEndpoint:
    """A single WhatsApp relay server endpoint."""
    ip: str
    port: int
    token: str = ""
    auth_token: str = ""
    raw_token: bytes = b""
    raw_auth_token: bytes = b""
    key: str = ""           # relay_key
    relay_id: int = 0
    relay_name: str = ""
    auth_token_id: str = ""
    protocol: int = 0
    c2r_rtt: Optional[int] = None   # client-to-relay RTT from WhatsApp server
    address_bytes: bytes = b""      # raw binary address from te2 node (IP+port)


@dataclass
class ParticipantInfo:
    """Participant entry from a <relay> node with pid and jid."""
    pid: int = 0
    jid: str = ""


@dataclass
class ParsedRelayAck:
    """Parsed relay information from an offer ack or structured relay node."""
    relays: list[RelayEndpoint] = field(default_factory=list)
    participants: list[ParticipantInfo] = field(default_factory=list)
    participant_jids: list[str] = field(default_factory=list)
    uuid: str = ""
    self_pid: Optional[int] = None
    peer_pid: Optional[int] = None
    hbh_key: Optional[bytes] = None
    rte: bytes = b""  # <rte> raw binary value from offer ack


@dataclass
class CallNodeInfo:
    """Extracted metadata from a <call> stanza."""
    tag: str = ""               # "offer" / "accept" / "transport" / etc.
    call_id: str = ""
    peer_jid: str = ""
    call_creator: str = ""
    peer_platform: str = ""
    peer_app_version: str = ""
    epoch_id: str = ""
    timestamp: str = ""
    inner_node: Any = None      # ProtocolTreeNode
