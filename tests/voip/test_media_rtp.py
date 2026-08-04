"""
Phase 2 tests — RTP packet encoding/decoding.

Tests: header roundtrip, packet roundtrip, session seq/ts increment,
WhatsApp fixture compatibility.
"""

import sys, os
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pytest
from voip.media.rtp import (
    RtpHeader, RtpPacket, RtpSession,
    RTP_PAYLOAD_TYPE_OPUS, RTP_EXTENSION_PROFILE, RTP_VERSION,
)


class TestRtpHeader:
    """RTP header encode/decode roundtrip tests."""

    def test_encode_decode_basic(self):
        """Basic header encode → decode roundtrip."""
        h = RtpHeader(
            payload_type=120, sequence_number=42, timestamp=123456,
            ssrc=0xABCDEF01, marker=True,
        )
        encoded = h.encode()
        assert len(encoded) == 12  # no CSRC, no extension

        decoded = RtpHeader.decode(encoded)
        assert decoded.version == RTP_VERSION
        assert decoded.payload_type == 120
        assert decoded.sequence_number == 42
        assert decoded.timestamp == 123456
        assert decoded.ssrc == 0xABCDEF01
        assert decoded.marker is True
        assert decoded.padding is False
        assert decoded.extension is False
        assert decoded.csrc_count == 0

    def test_encode_decode_with_extension(self):
        """Header with RTP extension (0xBEDE profile)."""
        h = RtpHeader(
            payload_type=120, sequence_number=100, timestamp=9999, ssrc=1,
            extension=True, extension_profile=0xBEDE, extension_data=b"\xAA\xBB\xCC\xDD",
        )
        encoded = h.encode()
        # 12 + 4 (ext header) + 4 (ext data) = 20
        assert len(encoded) == 20

        decoded = RtpHeader.decode(encoded)
        assert decoded.extension is True
        assert decoded.extension_profile == 0xBEDE
        assert decoded.extension_data == b"\xAA\xBB\xCC\xDD"

    def test_invalid_version_raises(self):
        """Invalid RTP version raises ValueError."""
        bad = bytearray(12)
        bad[0] = (1 << 6)  # version=1
        with pytest.raises(ValueError, match="Invalid RTP version"):
            RtpHeader.decode(bytes(bad))

    def test_too_short_raises(self):
        """Too-short data raises ValueError."""
        with pytest.raises(ValueError, match="too short"):
            RtpHeader.decode(b"\x80\x78\x00\x01")  # 4 bytes, need 12

    def test_all_fields_roundtrip(self):
        """All header fields survive encode→decode."""
        h = RtpHeader(
            version=2, padding=True, extension=True, csrc_count=1,
            marker=True, payload_type=120, sequence_number=65535,
            timestamp=0xFFFFFFFF, ssrc=0x12345678,
            csrc=[0xAAAAAAAA],
            extension_profile=0xBEDE, extension_data=b"\x01\x02\x03\x04",
        )
        encoded = h.encode()
        decoded = RtpHeader.decode(encoded)
        assert decoded.version == h.version
        assert decoded.padding == h.padding
        assert decoded.extension == h.extension
        assert decoded.csrc_count == h.csrc_count
        assert decoded.marker == h.marker
        assert decoded.payload_type == h.payload_type
        assert decoded.sequence_number == h.sequence_number
        assert decoded.timestamp == h.timestamp
        assert decoded.ssrc == h.ssrc
        assert decoded.csrc == h.csrc
        assert decoded.extension_profile == h.extension_profile
        assert decoded.extension_data == h.extension_data


class TestRtpPacket:
    """RTP packet (header + payload) roundtrip tests."""

    def test_packet_encode_decode(self):
        h = RtpHeader(payload_type=120, sequence_number=5, timestamp=100, ssrc=42)
        payload = b"hello rtp"
        pkt = RtpPacket(header=h, payload=payload)

        encoded = pkt.encode()
        decoded = RtpPacket.decode(encoded)
        assert decoded.header.sequence_number == 5
        assert decoded.payload == payload

    def test_is_rtp_detection(self):
        """is_rtp correctly identifies RTP packets."""
        h = RtpHeader(payload_type=120, sequence_number=0, timestamp=0, ssrc=1)
        pkt = RtpPacket(header=h, payload=b"data")
        encoded = pkt.encode()
        assert RtpPacket.is_rtp(encoded) is True

        # Non-RTP data
        assert RtpPacket.is_rtp(b"\x00\x00") is False  # version bits = 0
        assert RtpPacket.is_rtp(b"\x40\x00") is False  # version bits = 1
        assert RtpPacket.is_rtp(b"") is False


class TestRtpSession:
    """RtpSession sequence and timestamp management."""

    def test_session_seq_increments(self):
        sess = RtpSession.whatsapp_opus(ssrc=42)
        s1 = sess.create_packet(b"a").header
        s2 = sess.create_packet(b"b").header
        assert s2.sequence_number == (s1.sequence_number + 1) & 0xFFFF
        assert s2.timestamp == (s1.timestamp + 960) & 0xFFFFFFFF

    def test_session_random_init(self):
        """Different sessions start with different seq/ts."""
        s1 = RtpSession.whatsapp_opus(ssrc=1)
        s2 = RtpSession.whatsapp_opus(ssrc=2)
        # High probability of being different
        assert s1.sequence_number != s2.sequence_number or s1.timestamp != s2.timestamp

    def test_session_marker(self):
        """First packet has marker=True, subsequent have marker=False."""
        sess = RtpSession.whatsapp_opus(ssrc=1)
        p1 = sess.create_packet(b"first", marker=True)
        p2 = sess.create_packet(b"second", marker=False)
        assert p1.header.marker is True
        assert p2.header.marker is False

    def test_session_ssrc_preserved(self):
        sess = RtpSession.whatsapp_opus(ssrc=0xDEADBEEF)
        pkt = sess.create_packet(b"x")
        assert pkt.header.ssrc == 0xDEADBEEF

    def test_opus_defaults(self):
        sess = RtpSession.whatsapp_opus(ssrc=99)
        assert sess.payload_type == RTP_PAYLOAD_TYPE_OPUS
        assert sess.sample_rate == 16000
        assert sess.samples_per_packet == 960
