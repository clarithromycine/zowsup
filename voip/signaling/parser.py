"""
VoIP signaling parser — extracts structured data from WhatsApp XML nodes.

Handles:
- Relay endpoint extraction from <relay> nodes (attribute and structured formats)
- Relay ack parsing from offer responses (<iq><offer><relay>)
- Call node info extraction from <call> stanzas

Reference: WaCalls internal/voip/signaling/signaling_parse.go + relayack.go
"""

import base64
from typing import Optional

# Import ProtocolTreeNode type for type hints — the actual dependency is
# resolved at runtime via the zowsup core.
try:
    from core.structs import ProtocolTreeNode
except ImportError:
    ProtocolTreeNode = None  # type: ignore

from . import RelayEndpoint, ParsedRelayAck, CallNodeInfo, ParticipantInfo


def _attr_str(attrs: dict, key: str, default: str = "") -> str:
    """Safely get a string attribute from a node's attrs dict."""
    if attrs is None:
        return default
    return attrs.get(key, default) or default


def _attr_int(attrs: dict, key: str, default: int = 0) -> int:
    """Safely get an int attribute from a node's attrs dict."""
    val = _attr_str(attrs, key)
    if not val:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _node_children(node) -> list:
    """Get children of a ProtocolTreeNode."""
    if node is None:
        return []
    children = getattr(node, "children", None)
    if children is None:
        return []
    return children or []


def _node_data(node) -> Optional[bytes]:
    """Get data from a ProtocolTreeNode."""
    if node is None:
        return None
    return getattr(node, "data", None)


def _node_attrs(node) -> dict:
    """Get attributes dict from a ProtocolTreeNode."""
    if node is None:
        return {}
    attrs = getattr(node, "attributes", None)
    if attrs is None:
        return {}
    return attrs or {}


def _node_tag(node) -> str:
    """Get tag from a ProtocolTreeNode."""
    if node is None:
        return ""
    return getattr(node, "tag", "") or ""


def extract_node_info(node) -> Optional[CallNodeInfo]:
    """
    Extract call metadata from a <call> ProtocolTreeNode.

    Returns CallNodeInfo with tag, call_id, peer_jid, call_creator, etc.
    """
    if node is None:
        return None

    children = _node_children(node)
    if not children:
        return None

    inner = children[0]
    inner_tag = _node_tag(inner)

    node_attrs = _node_attrs(node)
    inner_attrs = _node_attrs(inner)

    return CallNodeInfo(
        tag=inner_tag,
        call_id=_attr_str(inner_attrs, "call-id"),
        peer_jid=_attr_str(node_attrs, "from"),
        peer_platform=_attr_str(node_attrs, "platform"),
        peer_app_version=_attr_str(node_attrs, "version"),
        call_creator=_attr_str(inner_attrs, "call-creator"),
        epoch_id=_attr_str(inner_attrs, "e"),
        timestamp=_attr_str(inner_attrs, "t"),
        inner_node=inner,
    )


def extract_relay_endpoints(node) -> list[RelayEndpoint]:
    """
    Extract relay endpoints from a call stanza inner node.

    Supports two formats:
    1. Attribute format: <relay ip="..." token="..." port="..."/>
    2. Structured format: <relay><te2><te ip="..." port="..."/></te2></relay>

    Reference: WaCalls signaling_parse.go ExtractRelayEndpoints()
    """
    relays: list[RelayEndpoint] = []

    def parse_relay_attrs(n) -> Optional[RelayEndpoint]:
        n_attrs = _node_attrs(n)
        ip = _attr_str(n_attrs, "ip")
        token = _attr_str(n_attrs, "token")
        if not ip or not token:
            return None
        key = _attr_str(n_attrs, "relay-key") or _attr_str(n_attrs, "key")
        port = _attr_int(n_attrs, "port", 3480)
        ep = RelayEndpoint(
            ip=ip,
            port=port,
            token=token,
            key=key,
            relay_id=_attr_int(n_attrs, "relay-id", 0),
        )
        if _attr_str(n_attrs, "c2r-rtt"):
            ep.c2r_rtt = _attr_int(n_attrs, "c2r-rtt")
        return ep

    for child in _node_children(node):
        child_tag = _node_tag(child)
        if child_tag == "relay":
            ep = parse_relay_attrs(child)
            if ep:
                relays.append(ep)
        elif child_tag == "relays":
            for rn in _node_children(child):
                if _node_tag(rn) == "relay":
                    ep = parse_relay_attrs(rn)
                    if ep:
                        relays.append(ep)

    # Sort by client-to-relay RTT (lowest first), nil RTT at end — matches Go sortRelaysByRtt
    relays.sort(key=lambda ep: (ep.c2r_rtt is None, ep.c2r_rtt or 0))

    return relays


def parse_relaylatency_te(rl_node) -> list[dict]:
    """Parse <te> children from a <relaylatency> node.

    Returns a list of dicts: {"relay_name": str, "ip": str, "port": int}.
    The <te> data is 6 bytes: 4B IP + 2B port (big-endian).
    """
    results = []
    if rl_node is None:
        return results
    for te_node in _node_children(rl_node):
        if _node_tag(te_node) != "te":
            continue
        data = _node_data(te_node)
        if not data or len(data) < 6:
            continue
        ip = ".".join(str(b) for b in data[0:4])
        port = (data[4] << 8) | data[5]
        relay_name = _attr_str(_node_attrs(te_node), "relay_name")
        results.append({"relay_name": relay_name, "ip": ip, "port": port})
    return results


def parse_relaylatency_te_entries(te_entries: list[dict]) -> list[dict]:
    """Parse <te> entries from a RelayLatencyCallProtocolEntity.te_entries.

    Each entry is {"latency": str, "relay_name": str, "data": bytes}.
    Returns a list of dicts: {"relay_name": str, "ip": str, "port": int}.
    """
    results = []
    for entry in te_entries or []:
        data = entry.get("data", b"")
        if not data or len(data) < 6:
            continue
        ip = ".".join(str(b) for b in data[0:4])
        port = (data[4] << 8) | data[5]
        relay_name = entry.get("relay_name", "")
        results.append({"relay_name": relay_name, "ip": ip, "port": port})
    return results


def parse_relay_node(relay_node) -> ParsedRelayAck:
    """Parse a single <relay> ProtocolTreeNode into ParsedRelayAck.

    Handles the structured relay format found in both:
      - Incoming <offer><relay> (callee receives relay info directly)
      - <iq><offer><relay> (caller receives relay info via offer ack)

    Format:
    <relay uuid="..." self_pid="..." peer_pid="...">
      <key>raw_key_bytes</key>
      <hbh_key>30_bytes_or_base64</hbh_key>
      <token id="0">raw_token_bytes</token>
      <auth_token id="0">raw_auth_token_bytes</auth_token>   <!-- optional -->
      <te2 relay_name=".." token_id="0" auth_token_id="0" c2r_rtt="55" protocol="1">
        [6-byte binary: IP(4) + port(2)]
      </te2>
      <participant jid="..."/>
    </relay>
    """
    import logging
    _log = logging.getLogger(__name__)

    result = ParsedRelayAck()

    if relay_node is None:
        return result

    r_attrs = _node_attrs(relay_node)
    result.uuid = _attr_str(r_attrs, "uuid")
    if "self_pid" in r_attrs:
        result.self_pid = _attr_int(r_attrs, "self_pid")
    if "peer_pid" in r_attrs:
        result.peer_pid = _attr_int(r_attrs, "peer_pid")

    relay_children = _node_children(relay_node)

    # Extract participants — capture BOTH pid and jid.
    # Multiple participants exist when the peer has multiple devices
    # (e.g. primary + companion), each with a distinct PID.
    for rc in relay_children:
        if _node_tag(rc) == "participant":
            jid = _attr_str(_node_attrs(rc), "jid")
            pid = _attr_int(_node_attrs(rc), "pid")
            if jid and jid not in result.participant_jids:
                result.participant_jids.append(jid)
            if jid:
                result.participants.append(ParticipantInfo(pid=pid, jid=jid))

    # Collect tokens, auth_tokens, key, hbh_key
    relay_key = ""
    tokens: dict[str, str] = {}
    auth_tokens: dict[str, str] = {}
    raw_tokens: dict[str, bytes] = {}
    raw_auth_tokens: dict[str, bytes] = {}

    for rc in relay_children:
        rc_tag = _node_tag(rc)
        data = _node_data(rc)

        if rc_tag == "key" and data:
            relay_key = data.decode("latin-1")
        elif rc_tag == "hbh_key" and data:
            if len(data) == 30:
                result.hbh_key = data
            elif len(data) > 30:
                try:
                    decoded = base64.b64decode(data)
                    if len(decoded) == 30:
                        result.hbh_key = decoded
                except Exception:
                    pass
        elif rc_tag == "token" and data:
            tid = _attr_str(_node_attrs(rc), "id", "0")
            tokens[tid] = base64.b64encode(data).decode()
            raw_tokens[tid] = data
        elif rc_tag == "auth_token" and data:
            tid = _attr_str(_node_attrs(rc), "id", "0")
            auth_tokens[tid] = base64.b64encode(data).decode()
            raw_auth_tokens[tid] = data

    # Parse te2 endpoints
    for rc in relay_children:
        if _node_tag(rc) != "te2":
            continue

        te2_attrs = _node_attrs(rc)
        te2_data = _node_data(rc)
        if not te2_data or len(te2_data) < 6:
            continue

        token_id = _attr_str(te2_attrs, "token_id", "0")
        auth_token_id = _attr_str(te2_attrs, "auth_token_id")
        relay_name = _attr_str(te2_attrs, "relay_name")
        protocol = _attr_int(te2_attrs, "protocol", 0)

        # IPv4 only: 6 bytes = 4B IP + 2B port
        if len(te2_data) == 6:
            ip = ".".join(str(b) for b in te2_data[0:4])
            port = (te2_data[4] << 8) | te2_data[5]
        else:
            continue

        if ip and port > 0:
            ep = _make_te2_endpoint(ip, port, relay_name,
                                    _attr_int(te2_attrs, "relay_id", 0),
                                    token_id, auth_token_id, protocol,
                                    tokens, raw_tokens, auth_tokens,
                                    raw_auth_tokens, relay_key, te2_attrs,
                                    te2_data)
            if ep:
                result.relays.append(ep)

    # Sort by client-to-relay RTT (lowest first)
    result.relays.sort(key=lambda ep: (ep.c2r_rtt is None, ep.c2r_rtt or 0))
    return result


def parse_relay_from_ack(ack_node) -> ParsedRelayAck:
    """Parse relay + participant info from an offer ack (<iq><offer>).

    Extracts <rte> and <user> from the ack wrapper, then delegates each
    <relay> child to parse_relay_node(). Returns a single ParsedRelayAck
    with all relays merged and participants deduplicated.
    """
    result = ParsedRelayAck()
    participant_seen: set[str] = set()

    def add_participant(jid: str):
        if jid and jid not in participant_seen:
            participant_seen.add(jid)
            result.participant_jids.append(jid)

    for child in _node_children(ack_node):
        child_tag = _node_tag(child)

        if child_tag == "user":
            for device_node in _node_children(child):
                if _node_tag(device_node) == "device":
                    jid = _attr_str(_node_attrs(device_node), "jid")
                    if jid:
                        add_participant(jid)

        elif child_tag == "rte":
            rte_data = _node_data(child)
            if rte_data:
                result.rte = rte_data  # keep raw bytes

        elif child_tag == "relay":
            sub = parse_relay_node(child)
            result.relays.extend(sub.relays)
            if sub.uuid:
                result.uuid = sub.uuid
            if sub.self_pid is not None:
                result.self_pid = sub.self_pid
            if sub.peer_pid is not None:
                result.peer_pid = sub.peer_pid
            if sub.hbh_key:
                result.hbh_key = sub.hbh_key
            for jid in sub.participant_jids:
                add_participant(jid)
            for pi in sub.participants:
                if pi.jid not in participant_seen:
                    participant_seen.add(pi.jid)
                    result.participants.append(pi)

    # Sort by client-to-relay RTT (lowest first), nil RTT at end
    result.relays.sort(key=lambda ep: (ep.c2r_rtt is None, ep.c2r_rtt or 0))
    return result


def _make_te2_endpoint(ip, port, relay_name, relay_id, token_id, auth_token_id,
                       protocol, tokens, raw_tokens, auth_tokens, raw_auth_tokens,
                       relay_key, attrs, address_bytes: bytes = b""):
    """Build a RelayEndpoint from parsed te2/te data.
    
    Mirrors Go relayack.go:
    - auth_token is only set when auth_token_id is explicitly provided
    - AddressBytes stores a copy of the raw binary address from te2 node
    """
    ep = RelayEndpoint(
        ip=ip,
        port=port,
        token=tokens.get(token_id, ""),
        raw_token=raw_tokens.get(token_id, b""),
        key=relay_key,
        relay_id=_attr_int(attrs, "relay_id", relay_id),
        relay_name=_attr_str(attrs, "relay_name") or relay_name,
        auth_token_id=auth_token_id if auth_token_id else token_id,
        protocol=protocol,
        c2r_rtt=_attr_int(attrs, "c2r_rtt") if _attr_str(attrs, "c2r_rtt") else None,
        address_bytes=bytes(address_bytes),
    )
    # Only populate auth_token fields when auth_token_id was EXPLICITLY set
    # (matches Go: if authTokenID != "" { ep.AuthToken = authTokens[authTokenID] })
    if auth_token_id:
        ep.auth_token = auth_tokens.get(auth_token_id, "")
        ep.raw_auth_token = raw_auth_tokens.get(auth_token_id, b"")
    return ep
