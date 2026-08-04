"""
Raw TURN relay test — WhatsApp v2.26 relay protocol.

WhatsApp encapsulates standard STUN/TURN messages with a 2-byte container prefix.
This script sends a raw STUN Allocate Request, strips the container from the
response, and extracts the XOR-MAPPED-ADDRESS.

Usage:
    python3 script/raw_turn_test.py <relay_ip> <auth_token> <key> [--port 3478]

The relay credentials (auth_token, key) come from the offer ack <relay> node:
    - auth_token: base64-decoded <auth_token> child data
    - key: base64-decoded <key> child data (relay_key)
"""

import asyncio
import struct
import os
import hmac
import hashlib
import argparse
import sys

# ── STUN constants ─────────────────────────────────────────────

STUN_MAGIC = 0x2112A442
STUN_ALLOCATE_REQUEST = 0x0003
STUN_ALLOCATE_SUCCESS = 0x0103
STUN_ALLOCATE_ERROR = 0x0113

ATTR_USERNAME = 0x0006
ATTR_MESSAGE_INTEGRITY = 0x0008
ATTR_LIFETIME = 0x000D
ATTR_XOR_RELAYED_ADDRESS = 0x0016
ATTR_REQUESTED_TRANSPORT = 0x0019
ATTR_DONT_FRAGMENT = 0x001A
ATTR_XOR_MAPPED_ADDRESS = 0x0020
ATTR_PRIORITY = 0x0024
ATTR_ICE_CONTROLLED = 0x8029
ATTR_ICE_CONTROLLING = 0x802A
ATTR_FINGERPRINT = 0x8028


# ── Helpers ────────────────────────────────────────────────────

def _encode_attr(attr_type: int, data: bytes) -> bytes:
    """Encode STUN TLV attribute with 4-byte alignment padding."""
    header = struct.pack("!HH", attr_type, len(data))
    padding = (4 - (len(data) % 4)) % 4
    return header + data + (b"\x00" * padding)


def _xor_decode_address(xor_data: bytes) -> tuple[str, int]:
    """Decode XOR-MAPPED-ADDRESS / XOR-RELAYED-ADDRESS."""
    # xor_data: 1B reserved, 1B family, 2B xor-port, 4B xor-ip
    family = xor_data[1]
    if family != 0x01:
        raise ValueError(f"Unsupported address family: {family}")
    xor_port = struct.unpack("!H", xor_data[2:4])[0]
    port = xor_port ^ (STUN_MAGIC >> 16)
    xor_ip = struct.unpack("!I", xor_data[4:8])[0]
    ip_int = xor_ip ^ STUN_MAGIC
    ip = ".".join(str((ip_int >> (24 - i * 8)) & 0xFF) for i in range(4))
    return ip, port


def build_stun_header(msg_type: int, body_len: int, txid: bytes) -> bytes:
    """Build 20-byte STUN header."""
    header = bytearray(20)
    struct.pack_into("!H", header, 0, msg_type)
    struct.pack_into("!H", header, 2, body_len)
    struct.pack_into("!I", header, 4, STUN_MAGIC)
    header[8:20] = txid
    return bytes(header)


def build_binding(auth_token: bytes, key: bytes) -> tuple[bytes, bytes]:
    """
    Build a minimal STUN Binding Request matching aioice's ICE check.
    Username = remote_ufrag:local_ufrag (ICE controlling convention)
    """
    import random
    txid = os.urandom(12)
    
    username = auth_token  # WhatsApp relay: no ICE colon-separator
    tiebreaker = struct.pack("!Q", random.getrandbits(64))
    
    attrs = bytearray()
    attrs.extend(_encode_attr(ATTR_USERNAME, username))
    attrs.extend(_encode_attr(ATTR_ICE_CONTROLLING, tiebreaker))
    attrs.extend(_encode_attr(ATTR_PRIORITY, struct.pack("!I", 0x7E0000FF)))
    
    mi_header = bytearray(20)
    struct.pack_into("!H", mi_header, 0, 0x0001)
    struct.pack_into("!H", mi_header, 2, len(attrs) + 24)
    struct.pack_into("!I", mi_header, 4, STUN_MAGIC)
    mi_header[8:20] = txid
    mac = hmac.new(key, digestmod=hashlib.sha1)
    mac.update(mi_header); mac.update(attrs)
    attrs.extend(_encode_attr(ATTR_MESSAGE_INTEGRITY, mac.digest()))
    
    from binascii import crc32
    fp_header = bytearray(20)
    struct.pack_into("!H", fp_header, 0, 0x0001)
    struct.pack_into("!H", fp_header, 2, len(attrs) + 8)
    struct.pack_into("!I", fp_header, 4, STUN_MAGIC)
    fp_header[8:20] = txid
    fp = crc32(fp_header + attrs) ^ 0x5354554E
    attrs.extend(_encode_attr(ATTR_FINGERPRINT, struct.pack("!I", fp & 0xFFFFFFFF)))
    
    header = build_stun_header(0x0001, len(attrs), txid)
    return bytes(header) + bytes(attrs), txid


def build_allocate(auth_token: bytes, key: bytes) -> tuple[bytes, bytes]:
    """
    Build a minimal STUN Allocate Request with WhatsApp credentials.

    Returns (full_stun_message, transaction_id).
    """
    txid = os.urandom(12)
    attrs = bytearray()

    # REQUESTED-TRANSPORT: UDP (protocol 17)
    attrs.extend(_encode_attr(ATTR_REQUESTED_TRANSPORT, bytes([17, 0, 0, 0])))

    # LIFETIME: 3600 seconds
    attrs.extend(_encode_attr(ATTR_LIFETIME, struct.pack("!I", 3600)))

    # DONT-FRAGMENT (no value)
    attrs.extend(_encode_attr(ATTR_DONT_FRAGMENT, b""))

    # USERNAME: auth_token (colon-joined with ? as per standard TURN)
    # WhatsApp may use auth_token directly
    attrs.extend(_encode_attr(ATTR_USERNAME, auth_token))

    # MESSAGE-INTEGRITY (HMAC-SHA1 over header + all prior attrs)
    mi_header = bytearray(20)
    struct.pack_into("!H", mi_header, 0, STUN_ALLOCATE_REQUEST)
    # +24 for the MESSAGE-INTEGRITY attr header (4) + value (20)
    struct.pack_into("!H", mi_header, 2, len(attrs) + 24)
    struct.pack_into("!I", mi_header, 4, STUN_MAGIC)
    mi_header[8:20] = txid

    mac = hmac.new(key, digestmod=hashlib.sha1)
    mac.update(mi_header)
    mac.update(attrs)
    attrs.extend(_encode_attr(ATTR_MESSAGE_INTEGRITY, mac.digest()))

    # FINGERPRINT (CRC32)
    fp_header = bytearray(20)
    struct.pack_into("!H", fp_header, 0, STUN_ALLOCATE_REQUEST)
    struct.pack_into("!H", fp_header, 2, len(attrs) + 8)
    struct.pack_into("!I", fp_header, 4, STUN_MAGIC)
    fp_header[8:20] = txid

    from binascii import crc32
    fingerprint = crc32(fp_header + attrs) ^ 0x5354554E
    attrs.extend(_encode_attr(ATTR_FINGERPRINT, struct.pack("!I", fingerprint & 0xFFFFFFFF)))

    # Build full message
    header = build_stun_header(STUN_ALLOCATE_REQUEST, len(attrs), txid)
    return bytes(header) + bytes(attrs), txid


def parse_stun_response(data: bytes) -> dict:
    """
    Parse a STUN response, handling WhatsApp container prefix.

    WhatsApp wraps STUN messages with a 2-byte big-endian length prefix
    (which includes the 20-byte STUN header). Multiple STUN messages may
    be concatenated in one UDP packet.

    Returns dict with keys: type, txid, xor_mapped, xor_relayed, error_code
    """
    results = []

    offset = 0
    while offset + 2 <= len(data):
        # WhatsApp container prefix
        container_len = struct.unpack("!H", data[offset:offset + 2])[0]
        offset += 2

        if offset + container_len > len(data):
            print(f"  [warn] container_len={container_len} exceeds remaining data, truncating")
            container_len = len(data) - offset

        stun = data[offset:offset + container_len]
        offset += container_len

        if len(stun) < 20:
            print(f"  [warn] STUN message too short: {len(stun)} bytes")
            continue

        msg_type = struct.unpack("!H", stun[0:2])[0]
        body_len = struct.unpack("!H", stun[2:4])[0]
        magic = struct.unpack("!I", stun[4:8])[0]
        txid = stun[8:20]

        type_names = {
            0x0001: "BindingReq", 0x0101: "BindingOK", 0x0111: "BindingErr",
            0x0003: "AllocReq", 0x0103: "AllocOK", 0x0113: "AllocErr",
        }
        type_name = type_names.get(msg_type, f"0x{msg_type:04x}")

        result = {
            "type": msg_type,
            "type_name": type_name,
            "txid": txid.hex(),
            "magic_ok": magic == STUN_MAGIC,
            "xor_mapped": None,
            "xor_relayed": None,
            "error_code": None,
        }

        # Parse attributes
        attr_data = stun[20:20 + body_len]
        aoff = 0
        while aoff + 4 <= len(attr_data):
            atype = struct.unpack("!H", attr_data[aoff:aoff + 2])[0]
            alen = struct.unpack("!H", attr_data[aoff + 2:aoff + 4])[0]
            aval = attr_data[aoff + 4:aoff + 4 + alen]
            # 4-byte alignment padding
            pad = (4 - (alen % 4)) % 4
            aoff += 4 + alen + pad

            if atype == ATTR_XOR_MAPPED_ADDRESS and alen >= 8:
                try:
                    result["xor_mapped"] = _xor_decode_address(aval[:8])
                except Exception as e:
                    result["xor_mapped"] = f"decode_err:{e}"
            elif atype == ATTR_XOR_RELAYED_ADDRESS and alen >= 8:
                try:
                    result["xor_relayed"] = _xor_decode_address(aval[:8])
                except Exception as e:
                    result["xor_relayed"] = f"decode_err:{e}"
            elif atype == 0x0009 and alen >= 4:
                # ERROR-CODE
                code_class = aval[2] & 0x07
                code_num = aval[3]
                reason = aval[4:].decode("utf-8", errors="replace")
                result["error_code"] = (code_class * 100 + code_num, reason)

        results.append(result)

    return results


# ── Main ───────────────────────────────────────────────────────


async def main():
    parser = argparse.ArgumentParser(description="Raw TURN relay test for WhatsApp v2.26")
    parser.add_argument("relay_ip", help="Relay server IP")
    parser.add_argument("auth_token", help="Auth token (hex-encoded)")
    parser.add_argument("key", help="Relay key (hex-encoded)")
    parser.add_argument("--port", type=int, default=3478, help="Relay port (default: 3478)")
    parser.add_argument("--binding", action="store_true", help="Send Binding instead of Allocate")
    args = parser.parse_args()

    auth_token = bytes.fromhex(args.auth_token)
    key = bytes.fromhex(args.key)

    print(f"Relay: {args.relay_ip}:{args.port}")
    print(f"Auth token ({len(auth_token)}B): {auth_token.hex()}")
    print(f"Key ({len(key)}B): {key.hex()[:40]}...")

    if args.binding:
        stun_msg, txid = build_binding(auth_token, key)
        print(f"\nBinding Request: {len(stun_msg)} bytes, txid={txid.hex()}")
    else:
        stun_msg, txid = build_allocate(auth_token, key)
        print(f"\nAllocate Request: {len(stun_msg)} bytes, txid={txid.hex()}")

    # Open UDP socket
    loop = asyncio.get_event_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)

    # Send
    sock.sendto(stun_msg, (args.relay_ip, args.port))
    print(f"Sent {'Binding' if args.binding else 'Allocate'} to {args.relay_ip}:{args.port}")

    # Receive
    try:
        data = await asyncio.wait_for(
            loop.sock_recv(sock, 4096),
            timeout=5.0,
        )
        print(f"\nReceived {len(data)} bytes")
        print(f"Raw hex (first 128): {data[:128].hex()}")

        # Parse
        results = parse_stun_response(data)
        for i, r in enumerate(results):
            print(f"\n--- Sub-message {i + 1} ---")
            print(f"  Type: {r['type_name']}")
            print(f"  Txid: {r['txid'][:16]}...")
            print(f"  Magic OK: {r['magic_ok']}")
            if r["error_code"]:
                print(f"  ERROR: {r['error_code']}")
            if r["xor_mapped"]:
                ip, port = r["xor_mapped"]
                print(f"  XOR-MAPPED-ADDRESS: {ip}:{port}")
            if r["xor_relayed"]:
                ip, port = r["xor_relayed"]
                print(f"  XOR-RELAYED-ADDRESS: {ip}:{port}")

    except asyncio.TimeoutError:
        print("\nTIMEOUT: No response from relay")

    sock.close()


if __name__ == "__main__":
    # Fix for missing import
    import socket
    asyncio.run(main())
