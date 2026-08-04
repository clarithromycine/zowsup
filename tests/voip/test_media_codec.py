"""
Phase 2 tests — Opus codec wrapper.

Tests: codec availability, encode/decode silence, frame size consistency,
NullCodec passthrough.
"""

import sys, os
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import math
import pytest
from voip.media.codec import OpusCodec, NullCodec, Codec


class TestNullCodec:
    """NullCodec (no-op) tests — always available."""

    def test_frame_size(self):
        c = NullCodec()
        assert c.frame_size() == 960
        assert c.sample_rate() == 16000

    def test_encode_decode_silence(self):
        c = NullCodec()
        pcm = [0.0] * 960
        encoded = c.encode(pcm)
        assert isinstance(encoded, bytes)
        assert len(encoded) > 0
        decoded = c.decode(encoded)
        assert len(decoded) == 960
        assert decoded == pcm

    def test_encode_decode_random(self):
        c = NullCodec()
        import random
        random.seed(123)
        pcm = [random.uniform(-0.5, 0.5) for _ in range(960)]
        encoded = c.encode(pcm)
        decoded = c.decode(encoded)
        # NullCodec should have perfect reconstruction (int16 roundtrip only)
        for i in range(len(pcm)):
            assert abs(decoded[i] - pcm[i]) < 0.001

    def test_is_codec_interface(self):
        c = NullCodec()
        assert isinstance(c, Codec)


class TestOpusCodec:
    """OpusCodec tests — requires libopus on the system."""

    @pytest.fixture
    def codec(self):
        c = OpusCodec()
        if not c.available:
            pytest.skip("libopus not available")
        yield c
        c.close()

    def test_available(self, codec):
        assert codec.available
        assert codec.frame_size() == 960
        assert codec.sample_rate() == 16000

    def test_encode_silence(self, codec):
        """Encoding silence produces valid Opus output."""
        pcm = [0.0] * 960
        encoded = codec.encode(pcm)
        assert isinstance(encoded, bytes)
        assert len(encoded) > 0
        # Opus silence frame is typically small
        assert len(encoded) < 200

    def test_decode_silence(self, codec):
        """Decoding an encoded silence frame returns ~silence."""
        pcm = [0.0] * 960
        encoded = codec.encode(pcm)
        decoded = codec.decode(encoded)
        assert len(decoded) == 960
        # All samples should be near zero
        max_abs = max(abs(v) for v in decoded)
        assert max_abs < 0.1, f"Silence decoded max abs = {max_abs}"

    def test_encode_decode_roundtrip_quality(self, codec):
        """Encode→decode maintains good quality for speech-like signals (correlation > 0.85)."""
        import math
        # Use a multi-tone signal (speech-like) instead of random noise
        pcm = [0.0] * 960
        for i in range(960):
            t = i / 16000.0
            pcm[i] = (
                0.4 * math.sin(2 * math.pi * 200 * t) +
                0.2 * math.sin(2 * math.pi * 500 * t) +
                0.1 * math.sin(2 * math.pi * 800 * t)
            )
        encoded = codec.encode(pcm)
        decoded = codec.decode(encoded)
        assert len(decoded) == 960

        # Find best cross-correlation offset (Opus has a small look-ahead delay)
        best_corr = -2.0
        for offset in range(0, min(300, len(pcm) - 100)):
            n = min(len(pcm) - offset, len(decoded))
            if n < 100:
                break
            orig = pcm[offset:offset + n]
            dec = decoded[:n]
            mean_o = sum(orig) / n
            mean_d = sum(dec) / n
            cov = sum((orig[i] - mean_o) * (dec[i] - mean_d) for i in range(n))
            var_o = sum((x - mean_o) ** 2 for x in orig)
            var_d = sum((x - mean_d) ** 2 for x in dec)
            if var_o > 0 and var_d > 0:
                corr = cov / math.sqrt(var_o * var_d)
                if corr > best_corr:
                    best_corr = corr
        assert best_corr > 0.85, f"Opus roundtrip correlation {best_corr:.4f} too low"

    def test_encode_rejects_wrong_size(self, codec):
        """encode() rejects input that isn't exactly frame_size() samples."""
        with pytest.raises(ValueError):
            codec.encode([0.0] * 100)  # wrong size

    def test_decode_short_frame(self, codec):
        """Decoding very short data returns some PCM samples (graceful degradation)."""
        decoded = codec.decode(b"\x00\x01")
        # Opus will decode whatever it can — might not be exactly 960
        # but should produce some output without crashing
        assert len(decoded) > 0

    def test_encode_produces_output(self, codec):
        """Encoding non-silence produces non-empty output."""
        import random
        random.seed(7)
        pcm = [random.uniform(-1.0, 1.0) for _ in range(960)]
        encoded = codec.encode(pcm)
        assert len(encoded) > 0

    def test_multiple_frames(self, codec):
        """Encode/decode multiple frames."""
        import random
        random.seed(99)
        for _ in range(5):
            pcm = [random.uniform(-0.5, 0.5) for _ in range(960)]
            encoded = codec.encode(pcm)
            decoded = codec.decode(encoded)
            assert len(decoded) == 960
