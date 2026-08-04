"""
Replay WhatsApp primary-device relay protocol and capture ALL responses.

Usage:
  1. Frida capture → copy one AllocReq hex + a 9079 audio frame hex
  2. Paste below
  3. Run: python script/replay_alloc.py
"""
import socket
import time
import struct
import binascii
import os
import select

# ── Config: paste hex from Frida capture ─────────────────────
ALLOC_REQ_HEX = """
0003014c 2112a442 b9113c3e e36d184e
f8d6175b 400000bf 090f01f5 cbd266db
3be7c385 5eb78662 de3b109f 64dc0d49
3bef10bb bf3c07d9 f295e4f1 27a40086
49af2d90 c312c819 7e48c30d 9053649e
0cbb9f40 38b07423 d3b57fdc ea056133
e233af67 240b9fab 87ca0158 15c7735a
50cee57f ffc3745b 78522457 7c4a17e3
34ac37f0 decc4a53 4c07e9fa 812bbc3a
be02a627 d714b102 8191779e 35d96f80
27531ba7 d6bdcead 30f6dd7e 79c0b0c0
ed54356f 2e8ee92a 74f88fd1 a74e2034
a07cf76f 403dd67c 38e353e5 93e8d43f
efc92c68 e8d54000 4024005f 0a0618e0
d1d1de07 0a081001 1893def0 ee070a08
1002189a ced4c109 0a080801 1885d5ee
cd0e0a09 08011001 18f5c6a7 3b0a0a08
01100218 90c0a8e0 090a0808 0218e198
ecae070a 0a080210 011891cd 97ea080a
0a080210 0218cdfc cd980c00 00160008
00012c84 bce2ab7c 00080014 9f98c465
9aad54a5 ecdc8967 4e79f107 07c188f3
"""

# Paste audio frames from Frida capture (9079/81ca/81c8 — one per """ block)
# Frames will be sent at 20ms intervals simulating real VoIP timing
AUDIO_FRAMES_HEX = [
    # Frame 1: initial 81ca control
    """81ca0007 7bd468e0 9030cf66 2dc7e93e
e27d1715 76142f87 10269e3d d1b5c891
80000001 cc6441f6 206156a7 1806""",
    # Frame 2: 9079 audio start
    """90790001 0000ce40 7bd468e0 debe0002
d3000047 68000000 590aad30 dd8f4237
675864dd fd6d6571 0db57bf3 734fd887
80""",
    # Add more frames from your capture below...
]

RELAY_IPS = ["157.240.15.62", "157.240.209.62", "57.144.45.54"]
RELAY_PORT = 3478
FRAME_INTERVAL_MS = 20  # VoIP audio frame interval
STUN_MAGIC = 0x2112A442
# ─────────────────────────────────────────────────────────────

def xor_addr(val: bytes) -> str:
    """Decode XOR-MAPPED/RELAYED-ADDRESS (8 bytes)."""
    family = val[1]
    if family != 1:
        return f"family={family}"
    xor_port = (val[2] << 8) | val[3]
    port = xor_port ^ (STUN_MAGIC >> 16)
    xor_ip = (val[4] << 24) | (val[5] << 16) | (val[6] << 8) | val[7]
    ip_int = xor_ip ^ STUN_MAGIC
    ip = f"{(ip_int>>24)&0xff}.{(ip_int>>16)&0xff}.{(ip_int>>8)&0xff}.{ip_int&0xff}"
    return f"{ip}:{port}"

def parse_stun(data: bytes) -> str:
    if len(data) < 20:
        return f"raw({len(data)}b)"
    msg_type = (data[0] << 8) | data[1]
    msg_len = (data[2] << 8) | data[3]
    magic = (data[4] << 24) | (data[5] << 16) | (data[6] << 8) | data[7]
    if magic != STUN_MAGIC:
        return f"nonSTUN({len(data)}b) first=0x{data[0]:02x}{data[1]:02x}"
    type_names = {0x0001:"BindingReq", 0x0101:"BindingOK", 0x0111:"BindingErr",
                  0x0003:"AllocReq", 0x0103:"AllocOK", 0x0113:"AllocErr",
                  0x0800:"WA_DATA", 0x0801:"Ping", 0x0802:"Pong"}
    tname = type_names.get(msg_type, f"STUN(0x{msg_type:04x})")
    txid = data[8:20].hex()
    attrs = []; pos = 20
    while pos + 4 <= len(data):
        at = (data[pos]<<8)|data[pos+1]; al = (data[pos+2]<<8)|data[pos+3]
        anames = {0x0008:"HMAC", 0x0016:"XOR-REL", 0x0020:"XOR-MAP",
                  0x4000:"SENDER-SUB", 0x4002:"0x4002", 0x4024:"SSRC-LIST", 0x802b:"0x802b"}
        an = anames.get(at, f"0x{at:04x}")
        val = data[pos+4:pos+4+al]
        if at in (0x0016, 0x0020): an += f"={xor_addr(val)}"
        elif al <= 8: an += f"={val.hex()}"
        else: an += f"({al}B)"
        attrs.append(an)
        pos += 4 + al + ((4 - (al%4))%4)
    return f"{tname} len={msg_len} txid={txid[:16]} attrs=[{','.join(attrs)}]"

def build_ping(txid: bytes = None) -> bytes:
    """Build STUN Ping (0x0801)."""
    if txid is None: txid = os.urandom(12)
    header = struct.pack("!HHI", 0x0801, 0, STUN_MAGIC) + txid
    return header

def recv_all(sock, timeout=2.0):
    """Non-blocking receive all pending packets."""
    end = time.time() + timeout
    pkts = []
    while time.time() < end:
        ready, _, _ = select.select([sock], [], [], max(0, end - time.time()))
        if not ready: break
        try:
            data, addr = sock.recvfrom(65536)
            pkts.append((addr, data))
        except socket.error:
            break
    return pkts

def print_pkts(pkts, label=""):
    if not pkts:
        print(f"  [{label}] (none)")
        return
    for addr, data in pkts:
        print(f"  ← [{label}] {addr[0]}:{addr[1]} ({len(data)}b)")
        print(f"     {parse_stun(data)}")
        h = data.hex()
        if len(h) <= 256: print(f"     hex: {h}")
        else: print(f"     hex: {h[:256]}\n          ...({len(data)-128} more bytes)")

def main():
    hex_str = ALLOC_REQ_HEX.replace("\n","").replace(" ","")
    alloc_req = binascii.unhexlify(hex_str)
    txid = alloc_req[8:20]
    
    # Parse audio frames
    audio_frames = []
    for af_hex in AUDIO_FRAMES_HEX:
        h = af_hex.replace("\n","").replace(" ","").strip()
        if h: audio_frames.append(binascii.unhexlify(h))
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", 0))
    local = sock.getsockname()[1]
    print(f"Local port: {local}")
    print(f"AllocReq txid: {txid.hex()}")
    print(f"Audio frames: {len(audio_frames)}")
    
    relay = RELAY_IPS[0]
    
    # ── Phase 1: AllocReq ──
    print(f"\n{'='*60}")
    print(f"Phase 1: AllocReq")
    print(f"{'='*60}")
    sock.sendto(alloc_req, (relay, RELAY_PORT))
    print_pkts(recv_all(sock, 2.0), "AllocResp")
    
    # ── Phase 2: Ping ──
    print(f"\n{'='*60}")
    print(f"Phase 2: Ping")
    print(f"{'='*60}")
    sock.sendto(build_ping(txid[:4] + os.urandom(8)), (relay, RELAY_PORT))
    print_pkts(recv_all(sock, 2.0), "PingResp")
    
    # ── Phase 3: Audio stream ──
    if audio_frames:
        print(f"\n{'='*60}")
        print(f"Phase 3: Audio stream ({len(audio_frames)} frames @ {FRAME_INTERVAL_MS}ms)")
        print(f"{'='*60}")
        
        total_incoming = []
        interval = FRAME_INTERVAL_MS / 1000.0
        
        for i, frame in enumerate(audio_frames):
            tag = f"{frame[0]:02x}{frame[1]:02x}"  # first 2 bytes of frame type
            sock.sendto(frame, (relay, RELAY_PORT))
            
            # Check for incoming (non-blocking, short timeout)
            pkts = recv_all(sock, max(0.001, interval * 0.3))
            if pkts:
                for addr, data in pkts:
                    print(f"  ← [frame#{i}] {addr[0]}:{addr[1]} ({len(data)}b) {parse_stun(data)}")
                total_incoming.extend(pkts)
            
            # Wait remaining interval
            time.sleep(interval * 0.7)
            
            if (i + 1) % 50 == 0:
                print(f"  ... sent {i+1}/{len(audio_frames)} frames, {len(total_incoming)} incoming so far")
        
        print(f"  Sent {len(audio_frames)} frames, got {len(total_incoming)} incoming packets")
    
    # ── Phase 4: Continuous listen ──
    print(f"\n{'='*60}")
    print(f"Phase 4: Continuous listen (15s)")
    print(f"{'='*60}")
    pkts = recv_all(sock, 15.0)
    print_pkts(pkts, "Idle")
    
    sock.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
