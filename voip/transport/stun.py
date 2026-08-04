"""
STUN message builder for WhatsApp VoIP relay registration.

Implements STUN Binding Request, Allocate Request, and WhatsApp Ping
message construction as used by the WhatsApp SCTP relay protocol.

Constants and message formats reverse-engineered from WhatsApp's relay
implementation.

Reference: WaCalls internal/voip/transport/stun.go
"""

import hmac
import hashlib
import struct
import os
from binascii import crc32


# ── STUN constants ─────────────────────────────────────────────

STUN_MAGIC_COOKIE = 0x2112A442
STUN_FINGERPRINT_XOR = 0x5354554E

# STUN message types
STUN_BINDING_REQUEST = 0x0001
STUN_ALLOCATE_REQUEST = 0x0003
WHATSAPP_PING = 0x0801
WHATSAPP_PONG = 0x0802

# STUN attribute types
ATTR_USERNAME = 0x0006
ATTR_MESSAGE_INTEGRITY = 0x0008
ATTR_LIFETIME = 0x000D
ATTR_XOR_RELAYED_ADDRESS = 0x0016
ATTR_REQUESTED_TRANSPORT = 0x0019
ATTR_PRIORITY = 0x0024
ATTR_SENDER_SUBSCRIPTIONS = 0x4000   # RELAY_TOKEN
ATTR_SSRC_LIST = 0x4024              # wa.voip.StreamDescriptors (WASM template)
ATTR_SENDER_SUBSCRIPTIONS_V2 = 0x4025  # wa.voip.SenderSubscriptions (APK only)
ATTR_ICE_CONTROLLED = 0x8029
ATTR_ICE_CONTROLLING = 0x802A
ATTR_FINGERPRINT = 0x8028

# ICE defaults
DEFAULT_ICE_PRIORITY = 16777215  # 0xFFFFFF


# ── Protobuf varint helpers (for subscription encoding) ────────


def _varint(value: int) -> bytes:
    """Encode unsigned integer as protobuf varint."""
    out = bytearray()
    v = value
    while v > 0x7F:
        out.append((v & 0x7F) | 0x80)
        v >>= 7
    out.append(v & 0x7F)
    return bytes(out)


def _pb_varint_field(field_number: int, value: int) -> bytes:
    """Protobuf varint field: tag + varint value."""
    tag = _varint(field_number << 3)
    return tag + _varint(value)


def _pb_length_delimited(field_number: int, data: bytes) -> bytes:
    """Protobuf length-delimited field: tag + length + data."""
    tag = _varint((field_number << 3) | 2)
    return tag + _varint(len(data)) + data


# ── Subscription encoding ──────────────────────────────────────


def build_sender_subscriptions(ssrc: int) -> bytes:
    """
    Build voip.SenderSubscriptions (WASM, attr 0x4000): one audio sender.

    message SenderSubscriptions {
      message Entry {
        uint32 ssrc = 3;
        uint32 stream_layer = 5;  // 0 = AUDIO
        uint32 payload_type = 6;  // 0 = MEDIA
      }
      repeated Entry entries = 1;
    }
    """
    inner = (
        _pb_varint_field(3, ssrc) +
        _pb_varint_field(5, 0) +
        _pb_varint_field(6, 0)
    )
    return _pb_length_delimited(1, inner)


# ── WASM StreamDescriptors template (attr 0x4024) ─────────────
# Fixed 86-byte protobuf from WhatsApp WASM/Web client.
# This is the SAME for every call — the relay identifies callers by
# the relay token (0x4000), not by SSRC subscription. The SSRC is
# only used for RTP-level stream identification.
# Reference: oxidezap/whatsapp-rust wacore/src/voip/stun.rs
WASM_STREAM_DESCRIPTORS_TEMPLATE = bytes([
    0x0a, 0x06, 0x18, 0xca, 0xbc, 0x85, 0xae, 0x04, 0x0a, 0x08, 0x10, 0x01, 0x18, 0xa5, 0xac, 0xaf,
    0xae, 0x0a, 0x0a, 0x08, 0x10, 0x02, 0x18, 0xd6, 0xa4, 0xe6, 0xf9, 0x0f, 0x0a, 0x08, 0x08, 0x01,
    0x18, 0xf7, 0xdd, 0x9e, 0xb6, 0x0a, 0x0a, 0x08, 0x01, 0x10, 0x01, 0x18, 0xab, 0xcc, 0xb1,
    0xf3, 0x0d, 0x0a, 0x0a, 0x08, 0x01, 0x10, 0x02, 0x18, 0xda, 0xda, 0xef, 0x8a, 0x05, 0x0a, 0x08,
    0x08, 0x02, 0x18, 0xc5, 0xe9, 0xec, 0x8e, 0x0b, 0x0a, 0x0a, 0x08, 0x02, 0x10, 0x01, 0x18, 0xfd,
    0xc2, 0xb1, 0xb6, 0x0f, 0x0a, 0x0a, 0x08, 0x02, 0x10, 0x02, 0x18, 0xb0, 0x97, 0xf7, 0xb2, 0x09,
])


def build_ssrc_subscription_list(
    self_ssrcs: list[int],
    peer_ssrcs: list[int],
    self_pid: int,
    peer_pid: int,
) -> bytes:
    """
    Build SSRC subscription list protobuf (Go reference format).

    Note: This format is NOT used for primary-device relay allocation.
    The WASM allocate uses WASM_STREAM_DESCRIPTORS_TEMPLATE instead.
    Kept for backward compatibility and tests.

    message SSRCSubscriptionList {
      message Entry {
        uint32 pid = 1;
        uint32 type = 2;   // 1 = active
        uint32 ssrc = 3;
      }
      repeated Entry entries = 1;
    }
    """
    entries = bytearray()

    for ssrc in self_ssrcs:
        if ssrc == 0:
            continue
        inner = (
            _pb_varint_field(1, self_pid) +
            _pb_varint_field(2, 1) +
            _pb_varint_field(3, ssrc)
        )
        entries.extend(_pb_length_delimited(1, inner))

    for ssrc in peer_ssrcs:
        if ssrc == 0:
            continue
        inner = (
            _pb_varint_field(1, peer_pid) +
            _pb_varint_field(2, 1) +
            _pb_varint_field(3, ssrc)
        )
        entries.extend(_pb_length_delimited(1, inner))

    return bytes(entries)


def build_ssrc_join_list(our_ssrc: int, peer_ssrc: int) -> bytes:
    """
    Build SSRC list for JOINING an existing relay session.

    Type 0 = "I own/send this SSRC", Type 1 = "I want to receive this SSRC".

    This tells the relay: "I'm SSRC X (type=0), I want SSRC Y (type=1)".
    """
    entries = bytearray()

    if our_ssrc:
        inner = (
            _pb_varint_field(1, 0) +  # pid
            _pb_varint_field(2, 0) +  # type=0 (sender)
            _pb_varint_field(3, our_ssrc)
        )
        entries.extend(_pb_length_delimited(1, inner))

    if peer_ssrc:
        inner = (
            _pb_varint_field(1, 0) +  # pid
            _pb_varint_field(2, 1) +  # type=1 (receiver)
            _pb_varint_field(3, peer_ssrc)
        )
        entries.extend(_pb_length_delimited(1, inner))

    return bytes(entries)


def build_ssrc_matrix(our_ssrc: int, peer_ssrc: int,
                      call_id: str = "", our_jid: str = "", peer_jid: str = "",
                      pid_jid_map: dict[int, str] = None) -> bytes:
    """
    Build the 9-entry SSRC matrix matching real Android device format.

    Real device sends pid=0/1/2 × type=0/1/2 matrix with UNIQUE SSRCs
    for each position, derived with different seeds.

    When pid_jid_map is provided (from <participant> elements in relay node),
    PID→JID assignment uses actual participant mapping instead of defaults.
    """
    from ..media.ssrc import generate_secure_ssrc

    entries = bytearray()

    def _entry(pid: int, typ: int, ssrc: int):
        inner = bytearray()
        if pid != 0:
            inner.extend(_pb_varint_field(1, pid))
        if typ != 0:
            inner.extend(_pb_varint_field(2, typ))
        inner.extend(_pb_varint_field(3, ssrc))
        entries.extend(_pb_length_delimited(1, bytes(inner)))

    # Determine JID for each PID.
    # Priority: pid_jid_map (from participant elements) > default mapping.
    def _jid_for_pid(pid: int) -> str:
        if pid_jid_map and pid in pid_jid_map:
            return pid_jid_map[pid]
        # Default: pid=0→our, pid=1→peer, pid=2→our
        if pid == 0:
            return our_jid or ""
        elif pid == 1:
            return peer_jid or ""
        else:
            return our_jid or ""

    if call_id:
        for pid in range(3):
            jid = _jid_for_pid(pid)
            for typ in range(3):
                seed = pid * 3 + typ
                ssrc = generate_secure_ssrc(call_id, jid, seed) if jid else our_ssrc
                _entry(pid, typ, ssrc)
    else:
        for pid, base_ssrc in [(0, our_ssrc), (1, peer_ssrc), (2, our_ssrc)]:
            for typ in range(3):
                _entry(pid, typ, base_ssrc)

    return bytes(entries)


# ── STUN attribute encoding ────────────────────────────────────


def _encode_attr(attr_type: int, data: bytes) -> bytes:
    """Encode a STUN TLV attribute with 4-byte alignment padding."""
    header = struct.pack("!HH", attr_type, len(data))
    padding_len = (4 - (len(data) % 4)) % 4
    return header + data + (b"\x00" * padding_len)


def _encode_xor_relayed_address(ip: str, port: int) -> bytes:
    """Encode XOR-RELAYED-ADDRESS attribute value."""
    data = bytearray(8)
    data[0] = 0x00  # reserved
    data[1] = 0x01  # IPv4
    # XOR port with upper 16 bits of magic cookie
    xor_port = port ^ (STUN_MAGIC_COOKIE >> 16)
    struct.pack_into("!H", data, 2, xor_port)
    # XOR IP with magic cookie
    parts = [int(x) for x in ip.split(".")]
    ip_int = (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]
    xor_ip = ip_int ^ STUN_MAGIC_COOKIE
    struct.pack_into("!I", data, 4, xor_ip)
    return bytes(data)


def _concat(*args: bytes) -> bytes:
    """Concatenate multiple byte strings."""
    return b"".join(args)


# ── Core STUN message builder ──────────────────────────────────


def _transaction_id() -> bytes:
    """Generate random 12-byte STUN transaction ID."""
    return os.urandom(12)


def build_stun_message(
    msg_type: int,
    attrs: bytes,
    transaction_id: bytes = None,
    integrity_key: bytes = None,
    include_fingerprint: bool = True,
) -> bytes:
    """
    Build a complete STUN message with optional MESSAGE-INTEGRITY and FINGERPRINT.

    Args:
        msg_type: STUN message type (e.g., 0x0001 for Binding Request)
        attrs: Pre-encoded attribute bytes
        transaction_id: 12-byte transaction ID (generated if None)
        integrity_key: HMAC-SHA1 key for MESSAGE-INTEGRITY attribute
        include_fingerprint: Whether to append CRC32 FINGERPRINT

    Returns:
        Complete STUN message bytes (header + attributes)
    """
    if transaction_id is None:
        transaction_id = _transaction_id()

    attrs_data = bytearray(attrs)

    # MESSAGE-INTEGRITY (must come before FINGERPRINT)
    if integrity_key is not None:
        # HMAC over: STUN header (type, length, magic, txid) + all prior attributes
        msg_len_for_hmac = len(attrs_data) + 24  # 20 header + 4 integrity header
        hmac_header = bytearray(20)
        struct.pack_into("!H", hmac_header, 0, msg_type)
        struct.pack_into("!H", hmac_header, 2, msg_len_for_hmac)
        struct.pack_into("!I", hmac_header, 4, STUN_MAGIC_COOKIE)
        hmac_header[8:20] = transaction_id

        mac = hmac.new(integrity_key, digestmod=hashlib.sha1)
        mac.update(hmac_header)
        mac.update(attrs_data)
        mi_attr = _encode_attr(ATTR_MESSAGE_INTEGRITY, mac.digest())
        attrs_data.extend(mi_attr)

    # FINGERPRINT (must be last attribute)
    if include_fingerprint:
        msg_len_for_crc = len(attrs_data) + 8  # 4 fingerprint header + 4 value
        crc_header = bytearray(20)
        struct.pack_into("!H", crc_header, 0, msg_type)
        struct.pack_into("!H", crc_header, 2, msg_len_for_crc)
        struct.pack_into("!I", crc_header, 4, STUN_MAGIC_COOKIE)
        crc_header[8:20] = transaction_id

        crc_input = bytes(crc_header) + bytes(attrs_data)
        fingerprint = crc32(crc_input) ^ STUN_FINGERPRINT_XOR
        fp_data = struct.pack("!I", fingerprint & 0xFFFFFFFF)
        fp_attr = _encode_attr(ATTR_FINGERPRINT, fp_data)
        attrs_data.extend(fp_attr)

    # Build STUN header
    header = bytearray(20)
    struct.pack_into("!H", header, 0, msg_type)
    struct.pack_into("!H", header, 2, len(attrs_data))
    struct.pack_into("!I", header, 4, STUN_MAGIC_COOKIE)
    header[8:20] = transaction_id

    return bytes(header) + bytes(attrs_data)


# ── High-level message builders ────────────────────────────────


def build_binding_request(
    username: bytes = None,
    hmac_key: bytes = None,
    sender_subscriptions: bytes = None,
    include_ice_controlling: bool = False,
    include_fingerprint: bool = True,
) -> bytes:
    """
    Build STUN Binding Request.

    Optional: USERNAME, PRIORITY, ICE-CONTROLLING, SENDER-SUBSCRIPTIONS,
    MESSAGE-INTEGRITY, FINGERPRINT.
    """
    txid = _transaction_id()
    parts = bytearray()

    if username and len(username) > 0:
        parts.extend(_encode_attr(ATTR_USERNAME, username))

    priority = struct.pack("!I", DEFAULT_ICE_PRIORITY)
    parts.extend(_encode_attr(ATTR_PRIORITY, priority))

    if include_ice_controlling:
        tiebreaker = os.urandom(8)
        parts.extend(_encode_attr(ATTR_ICE_CONTROLLING, tiebreaker))

    if sender_subscriptions:
        parts.extend(_encode_attr(ATTR_SENDER_SUBSCRIPTIONS, sender_subscriptions))

    key = hmac_key if hmac_key else None
    return build_stun_message(STUN_BINDING_REQUEST, bytes(parts), txid, key, include_fingerprint)


def build_allocate_request(
    sender_subscriptions: bytes,
    ssrc_list: bytes,
    hmac_key: bytes,
    relay_ip: str = "",
    relay_port: int = 0,
) -> bytes:
    """
    Build STUN Allocate Request for relay SSRC subscription.

    Includes: SENDER-SUBSCRIPTIONS, SSRC-LIST, optional XOR-RELAYED-ADDRESS,
    MESSAGE-INTEGRITY.
    """
    txid = _transaction_id()
    parts = bytearray()

    parts.extend(_encode_attr(ATTR_SENDER_SUBSCRIPTIONS, sender_subscriptions))
    parts.extend(_encode_attr(ATTR_SSRC_LIST, ssrc_list))

    if relay_ip and relay_port != 0:
        parts.extend(_encode_attr(
            ATTR_XOR_RELAYED_ADDRESS,
            _encode_xor_relayed_address(relay_ip, relay_port),
        ))

    return build_stun_message(STUN_ALLOCATE_REQUEST, bytes(parts), txid, hmac_key, False)


def build_whatsapp_ping() -> bytes:
    """Build WhatsApp custom STUN ping (0x0801). No attributes."""
    txid = _transaction_id()
    header = bytearray(20)
    struct.pack_into("!H", header, 0, WHATSAPP_PING)
    struct.pack_into("!H", header, 2, 0)  # zero-length body
    struct.pack_into("!I", header, 4, STUN_MAGIC_COOKIE)
    header[8:20] = txid
    return bytes(header)


# ── STUN response parsing ──────────────────────────────────────

ATTR_XOR_MAPPED_ADDRESS = 0x0020
ATTR_MAPPED_ADDRESS = 0x0001


def parse_stun_binding_response(data: bytes) -> tuple[str, int] | None:
    """Parse a STUN Binding Response to extract XOR-MAPPED-ADDRESS.

    Returns (ip, port) or None if not found.
    """
    if len(data) < 20:
        return None

    magic = struct.unpack("!I", data[4:8])[0]
    if magic != STUN_MAGIC_COOKIE:
        return None

    msg_type = struct.unpack("!H", data[0:2])[0]
    # 0x0101 = Binding Success Response
    if msg_type != 0x0101:
        return None

    msg_length = struct.unpack("!H", data[2:4])[0]
    offset = 20

    while offset + 4 <= 20 + msg_length and offset + 4 <= len(data):
        attr_type = struct.unpack("!H", data[offset:offset+2])[0]
        attr_length = struct.unpack("!H", data[offset+2:offset+4])[0]
        attr_data = data[offset+4:offset+4+attr_length]

        if attr_type == ATTR_XOR_MAPPED_ADDRESS and attr_length >= 8:
            return _parse_xor_mapped_address(attr_data)
        elif attr_type == ATTR_MAPPED_ADDRESS and attr_length >= 8:
            return _parse_mapped_address(attr_data)

        # Advance with padding
        padding = (4 - (attr_length % 4)) % 4
        offset += 4 + attr_length + padding

    return None


def _parse_xor_mapped_address(data: bytes) -> tuple[str, int] | None:
    """Parse XOR-MAPPED-ADDRESS attribute value (8 bytes for IPv4)."""
    if len(data) < 8:
        return None
    family = data[1]
    if family != 0x01:  # IPv4 only
        return None
    xor_port = struct.unpack("!H", data[2:4])[0]
    port = xor_port ^ (STUN_MAGIC_COOKIE >> 16)
    xor_ip = struct.unpack("!I", data[4:8])[0]
    ip_int = xor_ip ^ STUN_MAGIC_COOKIE
    ip = ".".join(str((ip_int >> shift) & 0xFF) for shift in (24, 16, 8, 0))
    return (ip, port)


def _parse_xor_mapped_from_stun(data: bytes) -> tuple[str, int] | None:
    """Parse XOR-MAPPED-ADDRESS from any STUN success response.
    
    Works for both BindingOK (0x0101) and AllocOK (0x0103).
    """
    if len(data) < 20:
        return None
    magic = struct.unpack("!I", data[4:8])[0]
    if magic != STUN_MAGIC_COOKIE:
        return None
    msg_length = struct.unpack("!H", data[2:4])[0]
    offset = 20
    while offset + 4 <= 20 + msg_length and offset + 4 <= len(data):
        attr_type = struct.unpack("!H", data[offset:offset+2])[0]
        attr_length = struct.unpack("!H", data[offset+2:offset+4])[0]
        attr_data = data[offset+4:offset+4+attr_length]
        if attr_type == ATTR_XOR_MAPPED_ADDRESS and attr_length >= 8:
            return _parse_xor_mapped_address(attr_data)
        elif attr_type == ATTR_MAPPED_ADDRESS and attr_length >= 8:
            return _parse_mapped_address(attr_data)
        padding = (4 - (attr_length % 4)) % 4
        offset += 4 + attr_length + padding
    return None


def _parse_mapped_address(data: bytes) -> tuple[str, int] | None:
    """Parse MAPPED-ADDRESS attribute value (8 bytes for IPv4)."""
    if len(data) < 8:
        return None
    family = data[1]
    if family != 0x01:  # IPv4 only
        return None
    port = struct.unpack("!H", data[2:4])[0]
    ip_int = struct.unpack("!I", data[4:8])[0]
    ip = ".".join(str((ip_int >> shift) & 0xFF) for shift in (24, 16, 8, 0))
    return (ip, port)


# ── STUN binding client ────────────────────────────────────────

async def stun_binding_request(
    stun_host: str,
    stun_port: int = 3478,
    timeout: float = 3.0,
) -> tuple[str, int] | None:
    """Send a STUN Binding Request and return the server-reflexive address.

    This is used to discover our public IP:port for P2P ICE candidates.

    Args:
        stun_host: STUN server hostname or IP.
        stun_port: STUN server port (default 3478).
        timeout: Response timeout in seconds.

    Returns:
        (ip, port) of our server-reflexive address, or None on failure.
    """
    import asyncio
    import logging
    _log = logging.getLogger(__name__)

    try:
        # Build a simple binding request (no auth, no fingerprint)
        request = build_binding_request(
            username=None,
            hmac_key=None,
            sender_subscriptions=None,
            include_ice_controlling=False,
            include_fingerprint=False,
        )

        loop = asyncio.get_event_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            asyncio.DatagramProtocol,
            local_addr=("0.0.0.0", 0),
        )

        local_addr = transport.get_extra_info("sockname")
        _log.debug("STUN binding: local=%s → %s:%d", local_addr, stun_host, stun_port)

        transport.sendto(request, (stun_host, stun_port))

        future = loop.create_future()

        original_protocol = protocol

        class _StunProtocol(asyncio.DatagramProtocol):
            def datagram_received(self, data, addr):
                if not future.done():
                    future.set_result(data)

        # Replace the protocol's datagram_received
        protocol.datagram_received = _StunProtocol().datagram_received

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            result = parse_stun_binding_response(response)
            if result:
                _log.info("STUN binding: srflx=%s:%d (local=%s)", result[0], result[1], local_addr)
            else:
                _log.warning("STUN binding: no XOR-MAPPED-ADDRESS in response")
            return result
        except asyncio.TimeoutError:
            _log.warning("STUN binding: timeout (%s:%d)", stun_host, stun_port)
            return None
        finally:
            transport.close()

    except Exception as e:
        _log.warning("STUN binding: error: %s", e)
        return None


# ── Packet classification ──────────────────────────────────────


def is_stun_packet(data: bytes) -> bool:
    """Check if data starts with STUN header (top 2 bits = 00)."""
    if len(data) < 2:
        return False
    return (data[0] & 0xC0) == 0


def is_rtp_packet(data: bytes) -> bool:
    """Check if data starts with RTP header (top 2 bits = 10)."""
    if len(data) < 2:
        return False
    return (data[0] & 0xC0) == 0x80
