"""
Phase 3 tests — STUN message builder.

Tests: Binding Request, Allocate Request, WhatsApp Ping,
MESSAGE-INTEGRITY, FINGERPRINT, packet classification.
"""

import sys, os
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import hmac
import hashlib
import struct
from binascii import crc32
import pytest
from voip.transport.stun import (
    build_binding_request,
    build_allocate_request,
    build_whatsapp_ping,
    build_sender_subscriptions,
    build_ssrc_subscription_list,
    build_stun_message,
    is_stun_packet,
    is_rtp_packet,
    STUN_MAGIC_COOKIE,
    STUN_BINDING_REQUEST,
    STUN_ALLOCATE_REQUEST,
    WHATSAPP_PING,
    ATTR_USERNAME,
    ATTR_MESSAGE_INTEGRITY,
    ATTR_FINGERPRINT,
    ATTR_SENDER_SUBSCRIPTIONS,
    ATTR_SSRC_LIST,
    STUN_FINGERPRINT_XOR,
)


def _parse_stun_header(data: bytes):
    """Parse STUN header: (msg_type, length, magic, transaction_id)."""
    msg_type = struct.unpack_from("!H", data, 0)[0]
    length = struct.unpack_from("!H", data, 2)[0]
    magic = struct.unpack_from("!I", data, 4)[0]
    txid = data[8:20]
    return msg_type, length, magic, txid


def _find_attr(data: bytes, attr_type: int) -> bytes | None:
    """Find a STUN attribute by type in the message body."""
    msg_type, msg_len, magic, txid = _parse_stun_header(data)
    offset = 20
    while offset + 4 <= 20 + msg_len and offset + 4 <= len(data):
        a_type = struct.unpack_from("!H", data, offset)[0]
        a_len = struct.unpack_from("!H", data, offset + 2)[0]
        if a_type == attr_type:
            return data[offset + 4:offset + 4 + a_len]
        padding = (4 - (a_len % 4)) % 4
        offset += 4 + a_len + padding
    return None


class TestStunConstants:
    def test_magic_cookie(self):
        assert STUN_MAGIC_COOKIE == 0x2112A442

    def test_fingerprint_xor(self):
        assert STUN_FINGERPRINT_XOR == 0x5354554E


class TestBuildWhatsAppPing:
    def test_ping_structure(self):
        ping = build_whatsapp_ping()
        msg_type, length, magic, txid = _parse_stun_header(ping)
        assert msg_type == WHATSAPP_PING  # 0x0801
        assert length == 0  # no body
        assert magic == STUN_MAGIC_COOKIE
        assert len(txid) == 12

    def test_ping_no_attributes(self):
        ping = build_whatsapp_ping()
        assert len(ping) == 20  # header only


class TestBuildBindingRequest:
    def test_minimal_binding(self):
        msg = build_binding_request(
            username=None, hmac_key=None,
            sender_subscriptions=None,
            include_ice_controlling=False,
            include_fingerprint=True,
        )
        msg_type, length, magic, txid = _parse_stun_header(msg)
        assert msg_type == STUN_BINDING_REQUEST
        assert magic == STUN_MAGIC_COOKIE

        # Should have PRIORITY and FINGERPRINT
        assert _find_attr(msg, ATTR_FINGERPRINT) is not None

    def test_binding_with_username(self):
        msg = build_binding_request(
            username=b"test_user:local_ufrag",
            hmac_key=b"secret_key",
            include_fingerprint=True,
        )
        username_data = _find_attr(msg, ATTR_USERNAME)
        assert username_data is not None
        assert username_data == b"test_user:local_ufrag"

        # Should have MESSAGE-INTEGRITY (because hmac_key provided)
        mi = _find_attr(msg, ATTR_MESSAGE_INTEGRITY)
        assert mi is not None
        assert len(mi) == 20  # SHA1 output

    def test_binding_with_ice_controlling(self):
        msg = build_binding_request(
            include_ice_controlling=True,
            include_fingerprint=False,
        )
        # ICE-CONTROLLING attribute (0x802A)
        ice = _find_attr(msg, 0x802A)
        assert ice is not None
        assert len(ice) == 8  # 8-byte tiebreaker

    def test_binding_with_subs(self):
        subs = build_sender_subscriptions(0x12345678)
        msg = build_binding_request(
            sender_subscriptions=subs,
            include_fingerprint=False,
        )
        sub_data = _find_attr(msg, ATTR_SENDER_SUBSCRIPTIONS)
        assert sub_data is not None

    def test_message_integrity_correct(self):
        """Verify MESSAGE-INTEGRITY HMAC is correct."""
        key = b"test_hmac_key"
        msg = build_binding_request(
            username=b"user:ufrag",
            hmac_key=key,
            include_fingerprint=False,
        )

        # Find MESSAGE-INTEGRITY value
        mi_val = _find_attr(msg, ATTR_MESSAGE_INTEGRITY)
        assert mi_val is not None

        # Recompute HMAC
        msg_type, msg_len, magic, txid = _parse_stun_header(msg)
        # Find the position of MESSAGE-INTEGRITY attribute
        offset = 20
        attrs_before_mi = bytearray()
        while offset + 4 <= 20 + msg_len:
            a_type = struct.unpack_from("!H", msg, offset)[0]
            a_len = struct.unpack_from("!H", msg, offset + 2)[0]
            if a_type == ATTR_MESSAGE_INTEGRITY:
                break
            padding = (4 - (a_len % 4)) % 4
            attrs_before_mi.extend(msg[offset:offset + 4 + a_len + padding])
            offset += 4 + a_len + padding

        # HMAC header: type(2) + adjusted_length(2) + magic(4) + txid(12)
        adjusted_len = len(attrs_before_mi) + 24
        hmac_header = struct.pack("!HHI", msg_type, adjusted_len, magic) + txid
        expected_mac = hmac.new(key, hmac_header + bytes(attrs_before_mi), hashlib.sha1).digest()
        assert mi_val == expected_mac


class TestBuildAllocateRequest:
    def test_allocate_structure(self):
        subs = build_sender_subscriptions(0x11111111)
        ssrc_list = build_ssrc_subscription_list([0xAAAA], [0xBBBB], 1, 2)
        msg = build_allocate_request(
            sender_subscriptions=subs,
            ssrc_list=ssrc_list,
            hmac_key=b"alloc_key",
            relay_ip="31.13.100.1",
            relay_port=3480,
        )
        msg_type, length, magic, txid = _parse_stun_header(msg)
        assert msg_type == STUN_ALLOCATE_REQUEST

        # Should NOT have FINGERPRINT
        assert _find_attr(msg, ATTR_FINGERPRINT) is None

        # Should have MESSAGE-INTEGRITY
        assert _find_attr(msg, ATTR_MESSAGE_INTEGRITY) is not None

        # Should have SENDER-SUBSCRIPTIONS
        assert _find_attr(msg, ATTR_SENDER_SUBSCRIPTIONS) is not None

        # Should have SSRC-LIST
        assert _find_attr(msg, ATTR_SSRC_LIST) is not None


class TestBuildSenderSubscriptions:
    def test_basic(self):
        data = build_sender_subscriptions(0x12345678)
        assert len(data) > 0
        # Re-parse: field 1 (length-delimited) containing field 3 (varint)
        assert isinstance(data, bytes)

    def test_different_ssrc(self):
        s1 = build_sender_subscriptions(0x1111)
        s2 = build_sender_subscriptions(0x2222)
        assert s1 != s2


class TestBuildSSRCSubscriptionList:
    def test_basic(self):
        data = build_ssrc_subscription_list([0xAAA], [0xBBB], 1, 2)
        assert len(data) > 0

    def test_empty(self):
        data = build_ssrc_subscription_list([], [], 0, 0)
        assert data == b""

    def test_skips_zero_ssrc(self):
        data = build_ssrc_subscription_list([0], [0xCCC], 0, 0)
        # self_ssrc=0 should be skipped, only peer_ssrc encoded
        assert len(data) > 0


class TestPacketClassification:
    def test_stun_detection(self):
        ping = build_whatsapp_ping()
        assert is_stun_packet(ping) is True

    def test_rtp_detection(self):
        # RTP header: version=2 → top 2 bits = 10
        rtp_header = bytes([0x80, 0x78, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        assert is_rtp_packet(rtp_header) is True

    def test_neither(self):
        # Non-STUN, non-RTP
        assert is_stun_packet(b"\x40\x00") is False
        assert is_rtp_packet(b"\x00\x00") is False
        assert is_stun_packet(b"") is False
        assert is_rtp_packet(b"") is False
