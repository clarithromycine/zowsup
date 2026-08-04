"""
Browser WebRTC PCM Bridge — connects a browser's audio to CallManager.

Establishes a WebRTC DataChannel ("pcm") with a browser, converting
between browser int16 LE PCM bytes and internal float32 PCM samples.

Flow:
  Browser mic  → DataChannel "pcm" (int16 LE) → float32 → CallManager.feed_audio()
  CallManager  → on_peer_audio (float32) → int16 LE → DataChannel "pcm" → Browser speaker

Usage:
    bridge = BrowserBridge(sdp_offer)
    bridge.on_browser_pcm = lambda pcm: cm.feed_audio(pcm)
    cm.on_peer_audio = lambda pcm: bridge.write_pcm(pcm)

    answer_sdp = await bridge.setup()
    # Return answer_sdp to browser

Reference: WaCalls cmd/server/bridge.go
"""

import asyncio
import logging
from typing import Optional, Callable

from .media.pcm import float32_to_int16le, int16le_to_float32

log = logging.getLogger(__name__)

PCM_CHANNEL_LABEL = "pcm"


class BrowserBridge:
    """
    Manages a WebRTC PeerConnection with a browser for PCM audio transport.

    A single bridge corresponds to one browser client connected to one call.
    """

    def __init__(self, sdp_offer: str, logger: logging.Logger = None):
        self._log = logger or log
        self._sdp_offer = sdp_offer
        self._pc = None
        self._dc = None

        # ── Callbacks ──────────────────────────────────────────

        # Called when browser sends PCM audio (int16 LE → float32)
        self.on_browser_pcm: Optional[Callable[[list[float]], None]] = None

        # Called when DataChannel opens
        self.on_open: Optional[Callable[[], None]] = None

        # Called when DataChannel closes
        self.on_close: Optional[Callable[[], None]] = None

        # Called on ICE failure
        self.on_ice_failed: Optional[Callable[[], None]] = None

    @property
    def ready(self) -> bool:
        """Whether the DataChannel is open and ready for PCM transfer."""
        return self._dc is not None and getattr(self._dc, "readyState", None) == "open"

    async def setup(self) -> str:
        """
        Process browser SDP offer and return SDP answer.

        Returns:
            SDP answer string to send back to the browser.
        """
        from aiortc import RTCPeerConnection, RTCSessionDescription

        self._pc = RTCPeerConnection()

        # ICE state tracking
        @self._pc.on("iceconnectionstatechange")
        async def on_ice_state():
            state = self._pc.iceConnectionState
            self._log.debug("BrowserBridge ICE: %s", state)
            if state == "failed" and self.on_ice_failed:
                self.on_ice_failed()

        # Handle browser-created DataChannel
        @self._pc.on("datachannel")
        def on_datachannel(channel):
            if channel.label == PCM_CHANNEL_LABEL:
                self._dc = channel
                self._log.info("BrowserBridge DataChannel received: %s", channel.label)

                @channel.on("message")
                def on_message(message):
                    self._handle_pcm_message(message)

                @channel.on("open")
                def on_open():
                    self._log.info("BrowserBridge DataChannel OPEN")
                    if self.on_open:
                        self.on_open()

                @channel.on("close")
                def on_close():
                    self._log.info("BrowserBridge DataChannel CLOSED")
                    if self.on_close:
                        self.on_close()
            else:
                self._log.debug("BrowserBridge ignoring DataChannel: %s", channel.label)

        # Set remote description (browser's offer)
        offer = RTCSessionDescription(sdp=self._sdp_offer, type="offer")
        await self._pc.setRemoteDescription(offer)

        # Create answer
        answer = await self._pc.createAnswer()
        await self._pc.setLocalDescription(answer)

        self._log.info("BrowserBridge setup complete")
        return self._pc.localDescription.sdp

    def _handle_pcm_message(self, message):
        """
        Handle incoming PCM from browser.

        Browser sends int16 LE bytes; we convert to float32 list.
        """
        if isinstance(message, str):
            return

        if not message or len(message) < 2:
            return

        try:
            pcm = int16le_to_float32(message)
            if self.on_browser_pcm and len(pcm) > 0:
                self.on_browser_pcm(pcm)
        except Exception as e:
            self._log.debug("BrowserBridge PCM decode error: %s", e)

    def write_pcm(self, pcm: list[float]) -> None:
        """
        Send PCM audio to the browser.

        Converts float32 list → int16 LE bytes → DataChannel send.

        Args:
            pcm: Float samples in [-1.0, 1.0]
        """
        if not self.ready:
            return

        if not pcm:
            return

        try:
            data = float32_to_int16le(pcm)
            self._dc.send(data)
        except Exception as e:
            self._log.debug("BrowserBridge PCM send error: %s", e)

    async def close(self) -> None:
        """Close the WebRTC connection."""
        if self._dc:
            try:
                self._dc.close()
            except Exception:
                pass
            self._dc = None

        if self._pc:
            try:
                await self._pc.close()
            except Exception:
                pass
            self._pc = None

        self._log.info("BrowserBridge closed")
