"""
Phase 2 tests — PCM conversion utilities.

Tests: float32→int16le→float32 roundtrip, boundary values,
sample accuracy (correlation > 0.9999).
"""

import sys, os
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import math
import pytest
from voip.media.pcm import float32_to_int16le, int16le_to_float32


class TestPcmConversion:

    def _correlation(self, a: list[float], b: list[float]) -> float:
        """Pearson correlation coefficient."""
        n = len(a)
        if n < 2:
            return 1.0 if a == b else 0.0
        mean_a = sum(a) / n
        mean_b = sum(b) / n
        cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
        var_a = sum((x - mean_a) ** 2 for x in a)
        var_b = sum((x - mean_b) ** 2 for x in b)
        if var_a == 0 and var_b == 0:
            return 1.0
        if var_a == 0 or var_b == 0:
            return 0.0
        return cov / math.sqrt(var_a * var_b)

    def test_roundtrip_silence(self):
        """Silence (all zeros) roundtrips perfectly."""
        pcm = [0.0] * 960
        encoded = float32_to_int16le(pcm)
        assert len(encoded) == 960 * 2  # 2 bytes per sample
        decoded = int16le_to_float32(encoded)
        assert decoded == pcm

    def test_roundtrip_random(self):
        """Random audio roundtrips with high accuracy."""
        import random
        random.seed(42)
        pcm = [random.uniform(-0.8, 0.8) for _ in range(960)]
        encoded = float32_to_int16le(pcm)
        decoded = int16le_to_float32(encoded)

        corr = self._correlation(pcm, decoded)
        assert corr > 0.9999, f"Correlation {corr} too low"

    def test_roundtrip_boundary_max(self):
        """+1.0 maps to 32767 and back."""
        pcm = [1.0] * 10
        encoded = float32_to_int16le(pcm)
        decoded = int16le_to_float32(encoded)
        # Should be very close to 1.0
        for v in decoded:
            assert abs(v - 1.0) < 0.001

    def test_roundtrip_boundary_min(self):
        """-1.0 maps to -32768 and back."""
        pcm = [-1.0] * 10
        encoded = float32_to_int16le(pcm)
        decoded = int16le_to_float32(encoded)
        for v in decoded:
            assert abs(v - (-1.0)) < 0.001

    def test_nan_handling(self):
        pcm = [float("nan"), 0.5, -0.3]
        encoded = float32_to_int16le(pcm)
        decoded = int16le_to_float32(encoded)
        # NaN should map to 0
        assert decoded[0] == 0.0
        assert abs(decoded[1] - 0.5) < 0.001

    def test_clipping_above_one(self):
        pcm = [1.5, 2.0, 100.0]
        encoded = float32_to_int16le(pcm)
        decoded = int16le_to_float32(encoded)
        for v in decoded:
            assert v <= 1.0

    def test_clipping_below_minus_one(self):
        pcm = [-1.5, -2.0, -100.0]
        encoded = float32_to_int16le(pcm)
        decoded = int16le_to_float32(encoded)
        for v in decoded:
            assert v >= -1.0

    def test_empty_input(self):
        assert float32_to_int16le([]) == b""
        assert int16le_to_float32(b"") == []

    def test_length_consistency(self):
        """N samples → 2N bytes → N samples."""
        for n in [1, 10, 100, 960]:
            pcm = [0.1] * n
            encoded = float32_to_int16le(pcm)
            assert len(encoded) == n * 2
            decoded = int16le_to_float32(encoded)
            assert len(decoded) == n
