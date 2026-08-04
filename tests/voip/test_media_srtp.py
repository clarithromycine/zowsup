"""
Phase 2 tests — SRTP encryption/decryption.

Tests: protect/unprotect roundtrip, auth tag verification, ROC wraparound,
IV generation, WhatsApp compatibility.
"""

import sys, os
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pytest
from voip.media.rtp import RtpHeader, RtpPacket, RtpSession
from voip.media.srtp import SrtpContext, SrtpError, SRTP_AUTH_TAG_LEN


# Test keying material
MK = b"\x01" * 16  # master key
MS = b"\x02" * 14  # master salt


class TestSrtpContext:
    """SRTP context initialization and key derivation."""

    def test_init_derives_keys(self):
        ctx = SrtpContext(MK, MS)
        assert len(ctx.session_key) == 16
        assert len(ctx.auth_key) == 20
        assert len(ctx.session_salt) == 14

    def test_init_rejects_bad_key_lengths(self):
        with pytest.raises(ValueError):
            SrtpContext(b"\x00" * 15, MS)  # key too short
        with pytest.raises(ValueError):
            SrtpContext(MK, b"\x00" * 13)  # salt too short

    def test_deterministic_key_derivation(self):
        """Same master key/salt → same session keys."""
        ctx1 = SrtpContext(MK, MS)
        ctx2 = SrtpContext(MK, MS)
        assert ctx1.session_key == ctx2.session_key
        assert ctx1.auth_key == ctx2.auth_key
        assert ctx1.session_salt == ctx2.session_salt

    def test_different_keys_differ(self):
        """Different master keys → different session keys."""
        ctx1 = SrtpContext(MK, MS)
        ctx2 = SrtpContext(b"\x03" * 16, MS)
        assert ctx1.session_key != ctx2.session_key


class TestSrtpProtectUnprotect:
    """SRTP protect → unprotect roundtrip."""

    def _make_packet(self, payload=b"test audio data", seq=42, ts=1000, ssrc=1):
        h = RtpHeader(payload_type=120, sequence_number=seq, timestamp=ts, ssrc=ssrc)
        return RtpPacket(header=h, payload=payload)

    def test_roundtrip_single_packet(self):
        ctx = SrtpContext(MK, MS)
        pkt = self._make_packet()
        encrypted = ctx.protect(pkt)

        # Should be larger than original (header + payload + auth_tag)
        assert len(encrypted) == pkt.header.size() + len(pkt.payload) + SRTP_AUTH_TAG_LEN

        decrypted = ctx.unprotect(encrypted)
        assert decrypted.header.sequence_number == pkt.header.sequence_number
        assert decrypted.payload == pkt.payload

    def test_roundtrip_multiple_packets(self):
        """Multiple packets with incrementing seq numbers."""
        ctx = SrtpContext(MK, MS)
        for seq in range(10):
            pkt = self._make_packet(payload=f"packet_{seq}".encode(), seq=seq)
            encrypted = ctx.protect(pkt)
            decrypted = ctx.unprotect(encrypted)
            assert decrypted.payload == f"packet_{seq}".encode()
            assert decrypted.header.sequence_number == seq

    def test_auth_tag_present(self):
        """Encrypted packet includes auth tag."""
        ctx = SrtpContext(MK, MS)
        pkt = self._make_packet(b"hello")
        encrypted = ctx.protect(pkt)
        # Auth tag should be at the end
        tag = encrypted[-SRTP_AUTH_TAG_LEN:]
        assert len(tag) == SRTP_AUTH_TAG_LEN

    def test_verify_valid_packet(self):
        ctx = SrtpContext(MK, MS)
        pkt = self._make_packet(b"verify me")
        encrypted = ctx.protect(pkt)
        assert ctx.verify(encrypted) is True

    def test_verify_tampered_packet(self):
        ctx = SrtpContext(MK, MS)
        pkt = self._make_packet(b"tamper test")
        encrypted = bytearray(ctx.protect(pkt))
        # Flip a bit in the payload area (after header)
        encrypted[20] ^= 0x01
        assert ctx.verify(bytes(encrypted)) is False

    def test_short_packet_raises(self):
        ctx = SrtpContext(MK, MS)
        with pytest.raises(SrtpError, match="too short"):
            ctx.unprotect(b"\x80\x78")  # 2 bytes

    def test_same_key_different_ssrc(self):
        """Packets with different SSRC use different IVs (different encryption)."""
        ctx = SrtpContext(MK, MS)
        p1 = self._make_packet(b"same", seq=1, ssrc=111)
        p2 = self._make_packet(b"same", seq=1, ssrc=222)
        enc1 = ctx.protect(p1)
        enc2 = ctx.protect(p2)
        # Same plaintext, different SSRC → different ciphertext
        assert enc1 != enc2

    def test_with_whatsapp_opus_session(self):
        """Test with RtpSession (WhatsApp Opus defaults)."""
        sess = RtpSession.whatsapp_opus(ssrc=0x12345678)
        ctx = SrtpContext(MK, MS)

        for _ in range(5):
            pkt = sess.create_packet(b"\x00" * 30, marker=False)
            encrypted = ctx.protect(pkt)
            decrypted = ctx.unprotect(encrypted)
            assert decrypted.payload == b"\x00" * 30


class TestSrtpRoc:
    """SRTP Rollover Counter (ROC) handling."""

    def test_roc_increment_on_wrap(self):
        ctx = SrtpContext(MK, MS)
        # Start near the end of sequence space
        pkt = RtpPacket(
            header=RtpHeader(sequence_number=65530, ssrc=1),
            payload=b"near wrap",
        )
        ctx.protect(pkt)
        assert ctx.roc == 0

        # Jump back to 0 (simulating wrap)
        pkt2 = RtpPacket(
            header=RtpHeader(sequence_number=5, ssrc=1),
            payload=b"after wrap",
        )
        ctx.protect(pkt2)
        assert ctx.roc == 1

    def test_packet_index_with_roc(self):
        ctx = SrtpContext(MK, MS)
        # Manually set ROC
        ctx.roc = 3
        ctx._initialized = True
        ctx._last_seq = 100

        idx = ctx._packet_index(200)
        # ROC=3, seq=200 → index = (3 << 16) | 200 = 196808
        assert idx == (3 << 16) | 200


class TestSrtpAuthTagVerification:
    """HMAC-SHA1 auth tag correctness."""

    def test_auth_tag_computed_correctly(self):
        ctx = SrtpContext(MK, MS)
        # Known test vector isn't available, but we can verify consistency
        data = b"test_auth_data"
        tag1 = ctx._compute_auth_tag(data)
        tag2 = ctx._compute_auth_tag(data)
        assert tag1 == tag2  # deterministic
        assert len(tag1) == 20  # SHA1 output

    def test_auth_tag_changes_with_data(self):
        ctx = SrtpContext(MK, MS)
        tag1 = ctx._compute_auth_tag(b"data1")
        tag2 = ctx._compute_auth_tag(b"data2")
        assert tag1 != tag2
