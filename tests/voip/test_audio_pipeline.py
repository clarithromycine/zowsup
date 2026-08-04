"""
Phase 4 tests — Audio pipeline (TxPipeline + RxPipeline).

Tests: PCM feed → encode → SRTP → decode → PCM output,
silence keepalive, full-duplex mock, STUN filtering.
"""

import sys, os
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import math
import pytest
from voip.media.codec import NullCodec
from voip.media.rtp import RtpHeader, RtpPacket, RtpSession
from voip.media.srtp import SrtpContext
from voip.media.pipeline import TxPipeline, RxPipeline


# Test keying material
MK = b"\x01" * 16
MS = b"\x02" * 14


class MockRelay:
    """Mock relay manager that collects sent data."""

    def __init__(self):
        self.sent: list[bytes] = []
        self._connected = True

    def broadcast(self, data: bytes):
        self.sent.append(data)

    def has_connection(self) -> bool:
        return self._connected


class TestTxPipeline:
    """Send pipeline tests."""

    def _make_tx(self, relay=None):
        codec = NullCodec()
        rtp = RtpSession.whatsapp_opus(ssrc=42)
        ctx = SrtpContext(MK, MS)
        return TxPipeline(codec, rtp, ctx, relay or MockRelay())

    def test_feed_exact_frame_sends(self):
        """Feeding exactly one frame triggers one send."""
        relay = MockRelay()
        tx = self._make_tx(relay)
        tx.feed_pcm([0.0] * 960)
        assert len(relay.sent) == 1

    def test_feed_multi_frame_sends_multiple(self):
        """Feeding 3 frames worth of PCM sends 3 packets."""
        relay = MockRelay()
        tx = self._make_tx(relay)
        tx.feed_pcm([0.1] * 960 * 3)
        assert len(relay.sent) == 3

    def test_feed_partial_accumulates(self):
        """Feeding less than a frame accumulates without sending."""
        relay = MockRelay()
        tx = self._make_tx(relay)
        tx.feed_pcm([0.0] * 500)
        assert len(relay.sent) == 0
        assert tx.pending_samples == 500

    def test_feed_across_boundaries(self):
        """Feeding across frame boundaries sends correctly."""
        relay = MockRelay()
        tx = self._make_tx(relay)
        # Feed 500 + 500 = 1000 → 1 full frame (960) + 40 pending
        tx.feed_pcm([0.0] * 500)
        tx.feed_pcm([0.1] * 500)
        assert len(relay.sent) == 1
        assert tx.pending_samples == 40

    def test_first_packet_has_marker(self):
        """First RTP packet has marker=True."""
        relay = MockRelay()
        tx = self._make_tx(relay)
        tx.feed_pcm([0.5] * 960)

        # Decode the sent SRTP back to RTP
        ctx = SrtpContext(MK, MS)
        pkt = ctx.unprotect(relay.sent[0])
        assert pkt.header.marker is True

    def test_subsequent_packets_no_marker(self):
        """Second packet has marker=False."""
        relay = MockRelay()
        tx = self._make_tx(relay)
        tx.feed_pcm([0.5] * 960 * 2)

        ctx = SrtpContext(MK, MS)
        pkt2 = ctx.unprotect(relay.sent[1])
        assert pkt2.header.marker is False

    def test_rtp_extension_set(self):
        """RTP extension (0xBEDE) is set on output packets."""
        relay = MockRelay()
        tx = self._make_tx(relay)
        tx.feed_pcm([0.0] * 960)

        ctx = SrtpContext(MK, MS)
        pkt = ctx.unprotect(relay.sent[0])
        assert pkt.header.extension is True
        assert pkt.header.extension_profile == 0xBEDE

    def test_silence_keepalive(self):
        """send_silence_frame() produces a valid SRTP packet."""
        relay = MockRelay()
        tx = self._make_tx(relay)
        tx.send_silence_frame()
        assert len(relay.sent) == 1

        # Verify it's valid SRTP
        ctx = SrtpContext(MK, MS)
        pkt = ctx.unprotect(relay.sent[0])
        assert len(pkt.payload) > 0

    def test_sequence_increments(self):
        """Sequence numbers increment across packets."""
        relay = MockRelay()
        tx = self._make_tx(relay)
        tx.feed_pcm([0.0] * 960 * 3)

        ctx = SrtpContext(MK, MS)
        seqs = []
        for data in relay.sent:
            pkt = ctx.unprotect(data)
            seqs.append(pkt.header.sequence_number)

        assert seqs[1] == (seqs[0] + 1) & 0xFFFF
        assert seqs[2] == (seqs[1] + 1) & 0xFFFF


class TestRxPipeline:
    """Receive pipeline tests."""

    def _make_rx(self):
        codec = NullCodec()
        ctx = SrtpContext(MK, MS)
        return RxPipeline(codec, ctx)

    def _encode_pcm(self, pcm):
        """Encode PCM through Tx side, return SRTP bytes."""
        codec = NullCodec()
        rtp = RtpSession.whatsapp_opus(ssrc=99)
        ctx = SrtpContext(MK, MS)
        relay = MockRelay()
        tx = TxPipeline(codec, rtp, ctx, relay)
        tx.feed_pcm(pcm)
        return relay.sent

    def test_decode_single_frame(self):
        """Rx decodes a single SRTP frame back to PCM."""
        rx = self._make_rx()
        decoded = []

        rx.on_audio = lambda pcm: decoded.extend(pcm)

        original = [0.1 * math.sin(2 * math.pi * 440 * i / 16000) for i in range(960)]
        srtp_packets = self._encode_pcm(original)

        for pkt in srtp_packets:
            ok = rx.handle_packet(pkt)
            assert ok is True

        assert len(decoded) == 960

    def test_stun_filtered(self):
        """STUN packets return False (not audio)."""
        rx = self._make_rx()

        # Build a fake STUN-like packet (top 2 bits = 00)
        stun_like = bytes([0x00, 0x01]) + b"\x00" * 18
        assert rx.handle_packet(stun_like) is False

    def test_empty_data(self):
        """Empty data returns False."""
        rx = self._make_rx()
        assert rx.handle_packet(b"") is False

    def test_garbage_srtp_handled(self):
        """Invalid SRTP data returns False (doesn't crash)."""
        rx = self._make_rx()
        # Data with RTP version=1 (not 2) — invalid RTP
        result = rx.handle_packet(b"\x40\x78" + b"\x00" * 100)
        # Should not raise — just return False
        assert result is False

    def test_full_duplex_mock(self):
        """Simultaneous send and receive using matching SRTP contexts."""
        # Two independent SRTP contexts for each direction
        mk_send = MK
        ms_send = MS
        mk_recv = b"\x03" * 16
        ms_recv = b"\x04" * 14

        codec = NullCodec()

        # Tx
        tx_srtp = SrtpContext(mk_send, ms_send)
        tx_rtp = RtpSession.whatsapp_opus(ssrc=111)
        tx_relay = MockRelay()
        tx = TxPipeline(codec, tx_rtp, tx_srtp, tx_relay)

        # Rx
        rx_srtp = SrtpContext(mk_send, ms_send)  # same context = same keys
        rx = RxPipeline(codec, rx_srtp)
        decoded_all = []
        rx.on_audio = lambda pcm: decoded_all.extend(pcm)

        # Send 3 frames
        original = [0.2] * 960 * 3
        tx.feed_pcm(original)

        # Receive them
        for pkt in tx_relay.sent:
            rx.handle_packet(pkt)

        assert len(decoded_all) == 960 * 3
        # NullCodec goes through float→int16→float quantization,
        # so values are approximate (within 1/32768)
        for i, (a, b) in enumerate(zip(decoded_all, original)):
            assert abs(a - b) < 0.001, f"sample {i}: {a} != {b}"

    def test_no_callback_does_not_crash(self):
        """Pipeline works without a PCM callback (just no delivery)."""
        rx = self._make_rx()
        rx.on_audio = None
        srtp_packets = self._encode_pcm([0.0] * 960)
        ok = rx.handle_packet(srtp_packets[0])
        assert ok is True  # Still processed, just not delivered
