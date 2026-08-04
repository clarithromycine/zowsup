"""VoipdClient — bridge to voipd Go daemon that handles all relay connections.

Replaces the aiortc-based relay.py PeerConnection logic.
Zowsup sends relay configs via UDP, voipd handles ICE/DTLS/SCTP/DataChannel
using pion/webrtc (same as wacalls).
"""

import asyncio
import json
import logging
import socket
from typing import Optional, Callable

log = logging.getLogger(__name__)

VOIPD_ADDR = ("127.0.0.1", 9999)


class VoipdClient:
    """UDP client for voipd. Handles relay config forwarding and data relay."""

    def __init__(self, daemon_addr=VOIPD_ADDR):
        self._addr = daemon_addr
        self._sock: Optional[socket.socket] = None
        self._on_state: Optional[Callable[[str, str], None]] = None  # (conn, state)
        self._on_data: Optional[Callable[[bytes], None]] = None
        self._recv_task: Optional[asyncio.Task] = None

    def on_state(self, fn: Callable[[str, str], None]):
        self._on_state = fn

    def on_data(self, fn: Callable[[bytes], None]):
        self._on_data = fn

    async def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)
        loop = asyncio.get_event_loop()
        self._recv_task = asyncio.ensure_future(self._recv_loop(loop))

    async def _recv_loop(self, loop):
        while self._sock:
            try:
                data = await loop.sock_recv(self._sock, 65536)
                for line in data.decode().strip().split("\n"):
                    if not line:
                        continue
                    msg = json.loads(line)
                    evt = msg.get("event")
                    if evt == "state" and self._on_state:
                        self._on_state(msg.get("conn", ""), msg.get("state", ""))
                    elif evt == "data" and self._on_data:
                        raw = bytes.fromhex(msg.get("data", ""))
                        self._on_data(raw)
            except Exception:
                await asyncio.sleep(0.1)

    def _send(self, obj: dict):
        if self._sock:
            self._sock.sendto((json.dumps(obj) + "\n").encode(), self._addr)

    def configure(self, relays: list[dict]):
        """Send relay configs to voipd. Each dict: ip, port, token, key, name,
        raw_token, raw_auth_token, auth_token, auth_token_id."""
        self._send({"cmd": "configure", "relays": relays})
        log.info("VoipdClient: configured %d relays", len(relays))

    def send(self, data: bytes):
        self._send({"cmd": "send", "data": data.hex()})

    async def close(self):
        if self._recv_task:
            self._recv_task.cancel()
            self._recv_task = None
        if self._sock:
            self._sock.close()
            self._sock = None
