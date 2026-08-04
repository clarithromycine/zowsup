"""
Test whether WhatsApp relay responds to STUN binding with SENDER-SUBSCRIPTIONS.

The relay may require STUN authentication BEFORE accepting DTLS.
This test sends the wacalls-style STUN binding with SSRC subscriptions.

Usage:
    python script/test_stun_relay.py <relay_ip> <token> <key> [--port 3478]
"""

import argparse
import hashlib
import hmac
import os
import socket
import struct
import sys
import time
from binascii import crc32

# ── STUN constants ─────────────────────────────────────────────
STUN_MAGIC_COOKIE = 0x2112A442
STUN_FINGERPRINT_XOR = 0x5354554E
STUN_BINDING_REQUEST = 0x0001
ATTR_USERNAME = 0x0006
ATTR_MESSAGE_INTEGRITY = 0x0008
ATTR_PRIORITY = 0x0024
ATTR_SENDER_SUBSCRIPTIONS = 0x4000
ATTR_ICE_CONTROLLING = 0x802A
ATTR_FINGERPRINT = 0x8028
DEFAULT_ICE_PRIORITY = 16777215


def varint(value: int) -> bytes:
    out = bytearray()
    v = value
    while v > 0x7F:
        out.append((v & 0x7F) | 0x80)
        v >>= 7
    out.append(v & 0x7F)
    return bytes(out)


def pb_varint_field(field_number: int, value: int) -> bytes:
    return varint(field_number << 3) + varint(value)


def pb_length_delimited(field_number: int, data: bytes) -> bytes:
    tag = varint((field_number << 3) | 2)
    return tag + varint(len(data)) + data


def build_sender_subscriptions(ssrc: int) -> bytes:
    inner = pb_varint_field(3, ssrc) + pb_varint_field(5, 0) + pb_varint_field(6, 0)
    return pb_length_delimited(1, inner)


def encode_attr(attr_type: int, data: bytes) -> bytes:
    header = struct.pack("!HH", attr_type, len(data))
    pad_len = (4 - (len(data) % 4)) % 4
    return header + data + (b"\x00" * pad_len)


def build_stun_binding(username: bytes, key: bytes, subs: bytes) -> bytes:
    """Build WhatsApp-style STUN binding with SENDER-SUBSCRIPTIONS."""
    txid = os.urandom(12)

    # Build attributes (before MESSAGE-INTEGRITY and FINGERPRINT)
    attrs = bytearray()

    if username:
        attrs.extend(encode_attr(ATTR_USERNAME, username))

    attrs.extend(encode_attr(ATTR_PRIORITY, struct.pack("!I", DEFAULT_ICE_PRIORITY)))

    tiebreaker = os.urandom(8)
    attrs.extend(encode_attr(ATTR_ICE_CONTROLLING, tiebreaker))

    if subs:
        attrs.extend(encode_attr(ATTR_SENDER_SUBSCRIPTIONS, subs))

    # MESSAGE-INTEGRITY (HMAC over header + attrs so far)
    mi_header = bytearray(20)
    mi_header[0:2] = struct.pack("!H", STUN_BINDING_REQUEST)
    mi_header[2:4] = struct.pack("!H", len(attrs) + 24)  # +24 for integrity attr
    mi_header[4:8] = struct.pack("!I", STUN_MAGIC_COOKIE)
    mi_header[8:20] = txid

    mac = hmac.new(key, mi_header + bytes(attrs), hashlib.sha1).digest()
    attrs.extend(encode_attr(ATTR_MESSAGE_INTEGRITY, mac))

    # FINGERPRINT (CRC32 over header + all attrs)
    fp_header = bytearray(20)
    fp_header[0:2] = struct.pack("!H", STUN_BINDING_REQUEST)
    fp_header[2:4] = struct.pack("!H", len(attrs) + 8)  # +8 for fingerprint attr
    fp_header[4:8] = struct.pack("!I", STUN_MAGIC_COOKIE)
    fp_header[8:20] = txid

    fp = crc32(fp_header + bytes(attrs)) ^ STUN_FINGERPRINT_XOR
    attrs.extend(encode_attr(ATTR_FINGERPRINT, struct.pack("!I", fp & 0xFFFFFFFF)))

    # Build header
    header = bytearray(20)
    header[0:2] = struct.pack("!H", STUN_BINDING_REQUEST)
    header[2:4] = struct.pack("!H", len(attrs))
    header[4:8] = struct.pack("!I", STUN_MAGIC_COOKIE)
    header[8:20] = txid

    return bytes(header) + bytes(attrs)


def is_stun_response(data: bytes) -> bool:
    if len(data) < 20:
        return False
    msg_type = struct.unpack("!H", data[0:2])[0]
    return msg_type in (0x0101, 0x0111)  # binding success or error


def test_stun_binding(ip: str, port: int, token: str, key: str, timeout: float = 5.0):
    print(f"Testing STUN binding to {ip}:{port} ...")
    print(f"  Token: {token[:20]}..." if len(token) > 20 else f"  Token: {token}")
    print(f"  Key: {key[:20]}..." if len(key) > 20 else f"  Key: {key}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    sock.connect((ip, port))

    # Generate dummy SSRC and build subscriptions
    ssrc = 0x12345678
    subs = build_sender_subscriptions(ssrc)

    # Build binding request
    local_ufrag = "test"
    username = f"{token}:{local_ufrag}".encode()
    hmac_key = key.encode() if isinstance(key, str) else key

    request = build_stun_binding(username, hmac_key, subs)
    print(f"  Sending STUN binding: {len(request)} bytes")
    print(f"  Username: {username.decode()}")
    sock.send(request)

    try:
        data = sock.recv(4096)
        print(f"  Received: {len(data)} bytes")
        print(f"  First 20 bytes: {data[:20].hex()}")

        if is_stun_response(data):
            msg_type = struct.unpack("!H", data[0:2])[0]
            if msg_type == 0x0101:
                print(f"  ✅ STUN binding SUCCESS!")
            else:
                # Try to extract error code
                print(f"  STUN error response")
                # Parse attributes for ERROR-CODE
                pos = 20
                while pos + 4 <= len(data):
                    attr_type, attr_len = struct.unpack("!HH", data[pos:pos+4])
                    if attr_type == 0x0009:  # ERROR-CODE
                        code = data[pos+6] * 100 + data[pos+7]
                        reason = data[pos+8:pos+4+attr_len].decode('utf-8', errors='replace')
                        print(f"  Error code: {code} - {reason}")
                    pos += 4 + attr_len + ((4 - (attr_len % 4)) % 4)
        else:
            print(f"  Non-STUN response received")
            print(f"  Hex: {data[:64].hex()}")

    except socket.timeout:
        print(f"  X No response (timeout)")

    sock.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ip")
    parser.add_argument("token")
    parser.add_argument("key")
    parser.add_argument("--port", type=int, default=3478)
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()

    test_stun_binding(args.ip, args.port, args.token, args.key, args.timeout)


if __name__ == "__main__":
    main()
