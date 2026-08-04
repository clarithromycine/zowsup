"""WhatsApp VoIP relay manager — raw UDP for primary device.

Primary devices use a non-WebRTC protocol:
  1. Send AllocReq directly to relay:3478
  2. Receive AllocOK (XOR-MAPPED-ADDRESS)
  3. Ping/Pong keepalive
  4. Send/receive 9079/81ca encrypted audio frames

Architecture:
  call_manager.py → RelayManager.configure_relays()
    → asyncio UDP socket → relay server
    → parse STUN responses → trigger on_connected / on_receive
"""

import asyncio
import logging
import struct
import time
from typing import Optional, Callable

from .stun import (
    build_whatsapp_ping,
    build_ssrc_matrix,
    _parse_xor_mapped_from_stun,
    STUN_MAGIC_COOKIE,
    build_stun_message,
    _encode_attr,
    _transaction_id,
)

log = logging.getLogger(__name__)

WA_RELAY_PORT = 3478
RELAY_KEEPALIVE_INTERVAL = 5.0
RELAY_ALLOC_TIMEOUT = 5.0
RELAY_ALLOC_MAX_RETRIES = 3
RELAY_IDLE_TIMEOUT = 30.0  # auto-disconnect if no data for 30s

# ── Audio test: paste 9079/81ca frame hexes from Frida capture ──
# These will be replayed after relay connects to verify audio path.
AUDIO_TEST_FRAMES = [
]


class RelayConfig:
    """Configuration for a single WhatsApp relay endpoint."""

    def __init__(
        self,
        ip: str,
        port: int = WA_RELAY_PORT,
        token: str = "",
        auth_token: str = "",
        raw_token: bytes = b"",
        raw_auth_token: bytes = b"",
        key: str = "",
        relay_id: int = 0,
        relay_name: str = "",
        auth_token_id: str = "",
        c2r_rtt: Optional[int] = None,
    ):
        self.ip = ip
        self.port = port
        self.token = token
        self.auth_token = auth_token
        self.raw_token = raw_token
        self.raw_auth_token = raw_auth_token
        self.key = key
        self.relay_id = relay_id
        self.relay_name = relay_name
        self.auth_token_id = auth_token_id
        self.c2r_rtt = c2r_rtt


class _RelayConnection:
    """Single relay UDP connection state."""

    def __init__(self, config: RelayConfig):
        self.config = config
        self.transport: Optional[asyncio.DatagramTransport] = None
        self._alloc_txid: Optional[bytes] = None
        self._alloc_done: asyncio.Event = asyncio.Event()
        self._connected = False
        self._ping_seq = 0

    @property
    def connected(self) -> bool:
        return self._connected

    def addr(self) -> tuple:
        return (self.config.ip, self.config.port)


class RelayManager:
    """Manages relay connections via raw UDP (primary device protocol)."""

    def __init__(self, logger: logging.Logger = None):
        self._log = logger or log
        self._audio_ssrc: int = 0
        self._subscription_ssrcs: list[int] = []
        self._self_pid: int = 0
        self._peer_pid: int = 0
        self._call_id: str = ""
        self._our_jid: str = ""
        self._peer_jid: str = ""
        self._pid_jid_map: dict[int, str] = {}  # PID→qualified JID from participants
        self._on_connected: Optional[Callable[[], None]] = None
        self._on_connect_failed: Optional[Callable[[], None]] = None
        self._on_receive: Optional[Callable[[bytes], None]] = None
        self._keepalive_task: Optional[asyncio.Task] = None
        self._keepalive_active: bool = False
        self._last_recv_time: float = 0.0
        self._connections: list[_RelayConnection] = []
        self._transport = None  # set when create_datagram_endpoint is called
        self._protocol = None  # set when create_datagram_endpoint is called
        self._audio_test_active = False
        self._srflx_address: Optional[tuple[str, int]] = None  # (ip, port) from relay STUN

    def set_ssrc(self, ssrc: int):
        self._audio_ssrc = ssrc

    def set_subscription_ssrcs(self, ssrcs: list[int]):
        """Set ALL subscription SSRCs (peer primary + companion devices)."""
        self._subscription_ssrcs = list(ssrcs) if ssrcs else []

    # Legacy compat: single SSRC
    def set_subscription_ssrc(self, ssrc: int):
        self._subscription_ssrcs = [ssrc] if ssrc else []

    def set_pid_jid_map(self, mapping: dict[int, str]):
        """Set PID→JID mapping from participants for SSRC matrix derivation."""
        self._pid_jid_map = dict(mapping) if mapping else {}

    def set_pids(self, self_pid: int, peer_pid: int):
        self._self_pid = self_pid
        self._peer_pid = peer_pid

    def set_call_info(self, call_id: str, our_jid: str, peer_jid: str):
        self._call_id = call_id
        self._our_jid = our_jid
        self._peer_jid = peer_jid

    def get_srflx_address(self) -> Optional[tuple[str, int]]:
        """Return (ip, port) discovered via relay STUN binding, or None."""
        return self._srflx_address

    def get_relay_entries(self) -> list[dict]:
        """Return relay info for relaylatency stanza: name, rtt, address bytes."""
        entries = []
        import ipaddress
        for conn in self._connections:
            if not conn.connected:
                continue
            cfg = conn.config
            if not cfg.relay_name:
                continue
            try:
                ip_int = int(ipaddress.IPv4Address(cfg.ip))
                addr = struct.pack("!IH", ip_int, cfg.port)
            except Exception:
                addr = b""
            entries.append({
                "relay_name": cfg.relay_name,
                "rtt_ms": cfg.c2r_rtt or 0,
                "addr_bytes": addr,
            })
        return entries

    def set_on_connected(self, fn: Callable[[], None]):
        self._on_connected = fn

    def set_on_connect_failed(self, fn: Callable[[], None]):
        self._on_connect_failed = fn

    def set_on_receive(self, fn: Callable[[bytes], None]):
        self._on_receive = fn

    def has_connection(self) -> bool:
        if not self._keepalive_active:
            return False
        if not any(c.connected for c in self._connections):
            return False
        # Idle timeout: if no data (audio or STUN) for too long, consider dead
        if self._last_recv_time > 0:
            idle = time.monotonic() - self._last_recv_time
            if idle > RELAY_IDLE_TIMEOUT:
                self._log.warning("relay idle timeout: %.0fs since last recv, disconnecting", idle)
                for c in self._connections:
                    c._connected = False
                return False
        return True

    def resend_subscriptions(self):
        """NO-OP: re-allocating resets relay media forwarding state.
        The real device only allocates ONCE. Keepalive is done via Ping,
        not re-allocation."""
        pass

    async def configure_relays(self, relays: list[RelayConfig]) -> None:
        """Send AllocReq to each relay and wait for AllocOK. Retries on timeout."""
        self._log.info("configure_relays: %d relays, ssrc=%d sub_ssrcs=%s",
                       len(relays), self._audio_ssrc, self._subscription_ssrcs)
        if not relays:
            self._log.warning("configure_relays: empty relay list, nothing to do")
            return

        loop = asyncio.get_event_loop()

        # Create one UDP socket shared across all relays
        class _Proto(asyncio.DatagramProtocol):
            def __init__(self, mgr):
                self.mgr = mgr

            def datagram_received(self, data, addr):
                self.mgr._handle_datagram(data, addr)

            def connection_lost(self, exc):
                pass

        transport, protocol = await loop.create_datagram_endpoint(
            lambda: _Proto(self),
            local_addr=("0.0.0.0", 0),
        )
        self._transport = transport
        self._protocol = protocol

        # Configure each relay
        self._connections = [_RelayConnection(r) for r in relays]


        #只选择c2r_rtt最小的哪个relay做连接测试
        self._connections.sort(key=lambda c: (c.config.c2r_rtt is None, c.config.c2r_rtt or 0))

        conn = self._connections[0]
        print("Selected relay for connection test:")
        print(conn.config)
        conn._alloc_done.clear()
        
        await self._send_allocate(conn)

        try:
            await asyncio.wait_for(
                conn._alloc_done.wait(),
                timeout=RELAY_ALLOC_TIMEOUT,
            )
        except asyncio.TimeoutError:
            pass

        if conn.connected:
            self._log.info("relay connected: %s:%d", conn.config.ip, conn.config.port)
            if self._on_connected:
                self._start_keepalive()
                self._on_connected()
            return
        
        else:
            self._log.warning("relay alloc timeout for %s:%d, trying all relays",
                              conn.config.ip, conn.config.port)
            
            self.on_connected = None  # prevent double-calling on_connected
            if self._on_connect_failed:
                self._on_connect_failed()

    async def _send_allocate(self, conn: _RelayConnection):
        """Build and send AllocReq for primary-device relay.

        Attributes:
          0x4000 — RELAY_TOKEN (raw_token bytes)
          0x4024 — SSRC-LIST (ONLY our SSRC, pid=0)
          0x0016 — XOR relay endpoint
          + MESSAGE-INTEGRITY

        Only our SSRC is listed. The relay auto-forwards other SSRCs
        in the same token session to us — listing the peer's SSRC
        would cause the relay to think it belongs to us too.
        """
        cfg = conn.config
        ssrc = self._audio_ssrc
        sub_ssrcs = self._subscription_ssrcs

        if ssrc == 0:
            self._log.warning("SSRC not set, skipping AllocReq")
            return

        hmac_key = cfg.key.encode() if cfg.key else b""

        if self._transport is None:
            self._log.warning("AllocReq skipped: transport closed (relay=%s:%d)",
                              cfg.ip, cfg.port)
            return

        self._log.debug("AllocReq params: key=%s raw_token[0:4]=%s ssrc=%d sub_ssrcs=%s",
                        cfg.key[:16] if len(cfg.key) > 16 else cfg.key,
                        cfg.raw_token[:4].hex(), ssrc, sub_ssrcs or [])

        # ── Step 1: Allocate (no Binding — Binding may interfere) ──
        attrs = bytearray()
        attrs.extend(_encode_attr(0x4000, cfg.raw_token))  # RELAY_TOKEN

        # 9-entry SSRC matrix with unique SSRCs per slot (matching real device).
        # Uses pid_jid_map when available for correct PID→JID assignment.
        primary_sub = sub_ssrcs[0] if sub_ssrcs else 0
        ssrc_list = build_ssrc_matrix(ssrc, primary_sub,
                                      self._call_id, self._our_jid, self._peer_jid,
                                      pid_jid_map=self._pid_jid_map)
        if ssrc_list:
            attrs.extend(_encode_attr(0x4024, ssrc_list))

        xor_rel = bytearray(8)
        xor_rel[0] = 0; xor_rel[1] = 1
        xor_port_val = cfg.port ^ (STUN_MAGIC_COOKIE >> 16)
        struct.pack_into("!H", xor_rel, 2, xor_port_val)
        parts_ip = [int(x) for x in cfg.ip.split(".")]
        ip_int = (parts_ip[0]<<24)|(parts_ip[1]<<16)|(parts_ip[2]<<8)|parts_ip[3]
        xor_ip_val = ip_int ^ STUN_MAGIC_COOKIE
        struct.pack_into("!I", xor_rel, 4, xor_ip_val)
        attrs.extend(_encode_attr(0x0016, bytes(xor_rel)))  # XOR-REL

        txid = _transaction_id()
        alloc_req = build_stun_message(0x0003, bytes(attrs), txid, hmac_key, False)

        conn._alloc_txid = alloc_req[8:20]
        self._transport.sendto(alloc_req, conn.addr())
        self._log.info("AllocReq → %s:%d txid=%s (%dB) hex=%s",
                       cfg.ip, cfg.port, conn._alloc_txid.hex()[:8], len(alloc_req),
                       alloc_req.hex())        

    def _handle_datagram(self, data: bytes, addr: tuple):
        """Handle incoming UDP datagram."""
        if len(data) < 20:
            return

        self._last_recv_time = time.monotonic()

        msg_type = (data[0] << 8) | data[1]
        magic = struct.unpack("!I", data[4:8])[0]

        if magic != STUN_MAGIC_COOKIE:
            # Non-STUN data — forward as audio.
            if not hasattr(self, '_nonstun_cnt'):
                self._nonstun_cnt = 0
            self._nonstun_cnt += 1
            # DEBUG only: per-packet logging is expensive (hex encode + I/O)
            if self._log.isEnabledFor(logging.DEBUG):
                self._log.debug("RELAY RECV #%d: len=%d type=%04x first16=%s",
                              self._nonstun_cnt, len(data),
                              msg_type, data[:16].hex())
            if self._on_receive:
                self._on_receive(data)
            return

        txid = data[8:20]

        # Find matching connection
        ip, port = addr
        conn = None
        for c in self._connections:
            if c.config.ip == ip:
                conn = c
                break

        if msg_type == 0x0103:  # AllocateSuccess
            self._log.info("AllocOK from %s:%d txid=%s", ip, port, txid.hex()[:8])
            # Parse XOR-MAPPED-ADDRESS (0x0020) from AllocOK to get our public IP:port
            srflx = _parse_xor_mapped_from_stun(data)
            if srflx:
                self._srflx_address = srflx
                self._log.warning("STUN srflx via AllocOK: %s:%d", srflx[0], srflx[1])
            if conn and not conn._connected:
                conn._connected = True
                conn._alloc_done.set()
                self._log.info("relay connected: %s:%d", ip, port)
                # Trigger on_connected immediately on first connection —
                # don't wait for all retries to finish.
                if self._on_connected and not any(
                    c._connected for c in self._connections
                    if c is not conn
                ):
                    self._start_keepalive()
                    self._on_connected()

        elif msg_type == 0x0001:  # BindingRequest from relay
            self._log.debug("BindingReq from %s:%d txid=%s", ip, port, txid.hex()[:8])
            self._send_binding_response(addr, txid)

        elif msg_type == 0x0101:  # BindingOK (response or ICE check)
            self._log.debug("BindingOK from %s:%d txid=%s", ip, port, txid.hex()[:8])

        elif msg_type == 0x0802:  # Pong
            self._log.debug("Pong from %s:%d", ip, port)

        elif msg_type == 0x0113:  # AllocateError
            self._log.error("AllocErr from %s:%d hex=%s", ip, port, data.hex())
        else:
            self._log.warning("UNHANDLED STUN type=0x%04x from %s:%d len=%d hex=%s",
                            msg_type, ip, port, len(data), data[:64].hex())

    def _send_binding_response(self, addr: tuple, txid: bytes):
        """Respond to relay's BindingRequest with BindingOK."""
        # Parse HMAC key from first connected relay
        hmac_key = b""
        for c in self._connections:
            if c.connected:
                hmac_key = c.config.key.encode() if c.config.key else b""
                break

        parts = bytearray()
        msg = build_stun_message(0x0101, bytes(parts), txid, hmac_key, False)
        self._transport.sendto(msg, addr)

    def _start_keepalive(self):
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
        self._keepalive_active = True
        self._keepalive_task = asyncio.ensure_future(self._keepalive_loop())

    async def _keepalive_loop(self):
        self.send(build_whatsapp_ping())
        while self._keepalive_active and self.has_connection():
            await asyncio.sleep(RELAY_KEEPALIVE_INTERVAL)
            if not self._keepalive_active or not self.has_connection():
                return
            self.send(build_whatsapp_ping())

    def send(self, data: bytes) -> None:
        """Send raw data to all connected relays."""
        if self._transport is None:
            return
        for conn in self._connections:
            if conn.connected:
                self._transport.sendto(data, conn.addr())

    def broadcast(self, data: bytes) -> None:
        if not hasattr(self, '_bc_cnt'):
            self._bc_cnt = 0
        self._bc_cnt += 1
        if self._bc_cnt <= 5 or self._bc_cnt % 100 == 0:
            self._log.info("RELAY TX #%d: len=%d type=%04x", self._bc_cnt, len(data),
                          (data[0]<<8)|data[1] if len(data)>=2 else 0)
        self.send(data)

    async def test_audio_replay(self, frames_hex: list[str], interval_ms: int = 20):
        """Replay captured 9079/81ca frames to relay for testing.
        
        Args:
            frames_hex: List of hex strings (space-separated ok) from Frida capture
            interval_ms: Interval between frames (default 20ms = standard VoIP)
        """
        frames = []
        for h in frames_hex:
            h = h.replace(" ", "").replace("\n", "")
            if h:
                frames.append(bytes.fromhex(h))
        
        if not frames:
            self._log.warning("test_audio_replay: no frames provided")
            return
        
        self._log.info("test_audio_replay: sending %d frames @ %dms", len(frames), interval_ms)
        interval = interval_ms / 1000.0
        self._audio_test_active = True
        
        for i, frame in enumerate(frames):
            if not self._audio_test_active:
                break
            tag = f"{frame[0]:02x}{frame[1]:02x}" if len(frame) >= 2 else "??"
            self.send(frame)
            self._log.debug("test_audio: [%d/%d] %s (%dB)", i+1, len(frames), tag, len(frame))
            await asyncio.sleep(interval)
        
        self._log.info("test_audio_replay: done (%d frames)", len(frames))

    async def close(self) -> None:
        self._audio_test_active = False
        self._keepalive_active = False
        self._last_recv_time = 0.0
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
        for conn in self._connections:
            conn._connected = False
        if self._transport:
            self._transport.close()
            self._transport = None
