"""
Phase 6 tests — Browser WebRTC Bridge.

Tests: PCM conversion through bridge, bridge lifecycle,
DataChannel message handling (mock), SDP offer/answer flow.
"""

import sys, os
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import math
import asyncio
import pytest
from voip.bridge import BrowserBridge, PCM_CHANNEL_LABEL
from voip.media.pcm import float32_to_int16le, int16le_to_float32


class TestBrowserBridgeBasic:
    def test_init(self):
        bridge = BrowserBridge("fake_sdp")
        assert bridge._sdp_offer == "fake_sdp"
        assert bridge.ready is False
        assert bridge.on_browser_pcm is None

    def test_pcm_channel_label(self):
        assert PCM_CHANNEL_LABEL == "pcm"


class TestPcmThroughBridge:
    """Test PCM float32 ↔ int16 conversion logic (the core of the bridge)."""

    def test_roundtrip_silence(self):
        """Silence PCM survives float32→int16→float32 roundtrip."""
        pcm = [0.0] * 960
        encoded = float32_to_int16le(pcm)
        decoded = int16le_to_float32(encoded)
        assert decoded == pcm

    def test_roundtrip_sine(self):
        """Sine wave roundtrip maintains high correlation."""
        pcm = [0.5 * math.sin(2 * math.pi * 440 * i / 16000) for i in range(960)]
        encoded = float32_to_int16le(pcm)
        decoded = int16le_to_float32(encoded)

        n = len(pcm)
        mean_o = sum(pcm) / n
        mean_d = sum(decoded) / n
        cov = sum((pcm[i] - mean_o) * (decoded[i] - mean_d) for i in range(n))
        var_o = sum((x - mean_o) ** 2 for x in pcm)
        var_d = sum((x - mean_d) ** 2 for x in decoded)
        corr = cov / math.sqrt(var_o * var_d) if var_o > 0 and var_d > 0 else 0
        assert corr > 0.9999

    def test_encoding_produces_2x_bytes(self):
        """N float samples → 2N bytes."""
        for n in [1, 10, 100, 480, 960]:
            pcm = [0.1] * n
            encoded = float32_to_int16le(pcm)
            assert len(encoded) == n * 2

    def test_boundary_clipping(self):
        """Values outside [-1, 1] are clipped."""
        pcm = [2.0, -2.0, 1.5, -1.5, 0.0]
        encoded = float32_to_int16le(pcm)
        decoded = int16le_to_float32(encoded)
        for v in decoded:
            assert -1.0 <= v <= 1.0


class TestBridgeCallback:
    """Test that bridge callbacks are properly set and callable."""

    def test_pcm_callback_settable(self):
        bridge = BrowserBridge("sdp")
        called = []

        bridge.on_browser_pcm = lambda pcm: called.append(len(pcm))

        # Simulate what _handle_pcm_message does
        pcm = [0.1] * 480
        encoded = float32_to_int16le(pcm)
        bridge._handle_pcm_message(encoded)

        assert len(called) == 1
        assert called[0] == 480

    def test_pcm_callback_ignores_empty(self):
        bridge = BrowserBridge("sdp")
        called = []

        bridge.on_browser_pcm = lambda pcm: called.append(True)
        bridge._handle_pcm_message(b"")  # empty
        bridge._handle_pcm_message(b"\x00")  # 1 byte, too short

        assert len(called) == 0

    def test_pcm_callback_ignores_string(self):
        bridge = BrowserBridge("sdp")
        called = []

        bridge.on_browser_pcm = lambda pcm: called.append(True)
        bridge._handle_pcm_message("not bytes")

        assert len(called) == 0

    def test_open_close_callbacks(self):
        bridge = BrowserBridge("sdp")
        open_called = []
        close_called = []

        bridge.on_open = lambda: open_called.append(True)
        bridge.on_close = lambda: close_called.append(True)

        assert bridge.on_open is not None
        assert bridge.on_close is not None

    def test_ready_state(self):
        bridge = BrowserBridge("sdp")
        assert bridge.ready is False  # No DC yet


class TestBridgeWritePcm:
    """Test write_pcm behavior without actual WebRTC (graceful no-op)."""

    def test_write_pcm_without_dc(self):
        """write_pcm when not ready should not raise."""
        bridge = BrowserBridge("sdp")
        bridge.write_pcm([0.1] * 960)  # No DC — should not crash

    def test_write_pcm_empty(self):
        bridge = BrowserBridge("sdp")
        bridge.write_pcm([])  # Empty list — should not crash

    def test_write_pcm_none_ready(self):
        bridge = BrowserBridge("sdp")
        bridge.write_pcm(None)  # None — shouldn't get here but handle gracefully
        # This would actually raise TypeError on iteration, which is fine
        # as the caller should never pass None


class TestBridgeClose:
    def test_close_without_setup(self):
        """Close before setup should not raise."""
        import asyncio
        bridge = BrowserBridge("sdp")

        async def _run():
            await bridge.close()

        asyncio.run(_run())

    def test_close_idempotent(self):
        """Multiple close calls should not raise."""
        import asyncio
        bridge = BrowserBridge("sdp")

        async def _run():
            await bridge.close()
            await bridge.close()

        asyncio.run(_run())


class TestBridgeLifecycle:
    """Test full IPC-like flow (two aiortc peers talking to each other)."""

    @pytest.mark.asyncio
    async def test_two_peer_sdp_exchange_and_pcm(self):
        """
        Set up two aiortc peers: one as "browser", one as our bridge.
        Verify PCM data flows in both directions.
        """
        from aiortc import RTCPeerConnection, RTCSessionDescription

        # --- Browser side ---
        browser_pc = RTCPeerConnection()
        browser_dc = browser_pc.createDataChannel(PCM_CHANNEL_LABEL)

        browser_received = []

        @browser_dc.on("message")
        def on_browser_message(message):
            if isinstance(message, bytes):
                browser_received.append(message)

        browser_offer = await browser_pc.createOffer()
        await browser_pc.setLocalDescription(browser_offer)

        # --- Bridge side ---
        bridge = BrowserBridge(browser_pc.localDescription.sdp)
        bridge_received = []
        bridge.on_browser_pcm = lambda pcm: bridge_received.append(pcm)

        answer_sdp = await bridge.setup()

        # --- Complete handshake ---
        answer = RTCSessionDescription(sdp=answer_sdp, type="answer")
        await browser_pc.setRemoteDescription(answer)

        # Wait for DataChannel open
        await _wait_dc_open(browser_dc)

        # --- Test browser → bridge (mic direction) ---
        mic_pcm = [0.1 * math.sin(2 * math.pi * 440 * i / 16000) for i in range(480)]
        browser_dc.send(float32_to_int16le(mic_pcm))
        await asyncio.sleep(0.3)

        assert len(bridge_received) >= 1, "Bridge should have received PCM"
        # Verify PCM survived the trip
        for v in bridge_received[0]:
            assert -1.0 <= v <= 1.0

        # --- Test bridge → browser (speaker direction) ---
        speaker_pcm = [0.2 * math.sin(2 * math.pi * 880 * i / 16000) for i in range(480)]
        bridge.write_pcm(speaker_pcm)
        await asyncio.sleep(0.3)

        assert len(browser_received) >= 1, "Browser should have received PCM"
        decoded = int16le_to_float32(browser_received[-1])
        assert len(decoded) == 480

        # --- Cleanup ---
        await bridge.close()
        await browser_pc.close()

    @pytest.mark.asyncio
    async def test_bidirectional_pcm_flow(self):
        """Send PCM both ways and verify both sides receive correctly."""
        from aiortc import RTCPeerConnection, RTCSessionDescription

        # Browser
        browser_pc = RTCPeerConnection()
        browser_dc = browser_pc.createDataChannel(PCM_CHANNEL_LABEL)
        browser_received_all = []

        @browser_dc.on("message")
        def on_msg(message):
            if isinstance(message, bytes):
                browser_received_all.append(message)

        offer = await browser_pc.createOffer()
        await browser_pc.setLocalDescription(offer)

        # Bridge
        bridge = BrowserBridge(browser_pc.localDescription.sdp)
        bridge_received_all = []
        bridge.on_browser_pcm = lambda pcm: bridge_received_all.extend(pcm)

        answer = await bridge.setup()
        await browser_pc.setRemoteDescription(RTCSessionDescription(sdp=answer, type="answer"))
        await _wait_dc_open(browser_dc)

        # Send 5 frames each way
        for _ in range(5):
            browser_dc.send(float32_to_int16le([0.3] * 240))
            bridge.write_pcm([0.7] * 240)
            await asyncio.sleep(0.05)

        await asyncio.sleep(0.3)

        assert len(bridge_received_all) >= 240  # At least one frame received
        assert len(browser_received_all) >= 1   # At least one frame received

        # Decode browser-received data
        total_browser_samples = sum(
            len(int16le_to_float32(d)) for d in browser_received_all
        )
        assert total_browser_samples >= 240

        await bridge.close()
        await browser_pc.close()


async def _wait_dc_open(dc, timeout: float = 5.0):
    """Wait for a DataChannel to reach 'open' state."""
    import asyncio
    import time
    start = time.time()
    while getattr(dc, "readyState", None) != "open":
        await asyncio.sleep(0.05)
        if time.time() - start > timeout:
            raise TimeoutError("DataChannel did not open")
