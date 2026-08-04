"""
Test whether relay responds to STUN AFTER a DTLS ClientHello is sent first.

The relay may require a DTLS handshake initiation before accepting STUN.

Usage:
    python script/test_dtls_then_stun.py <relay_ip> <token> <key>
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
from OpenSSL import SSL

STUN_MAGIC = 0x2112A442
STUN_BINDING = 0x0001
ATTR_USERNAME = 0x0006
ATTR_MESSAGE_INTEGRITY = 0x0008
ATTR_PRIORITY = 0x0024
ATTR_SENDER_SUBSCRIPTIONS = 0x4000
ATTR_ICE_CONTROLLING = 0x802A
ATTR_FINGERPRINT = 0x8028


def varint(v):
    out = bytearray()
    while v > 0x7F:
        out.append((v & 0x7F) | 0x80)
        v >>= 7
    out.append(v & 0x7F)
    return bytes(out)


def pb_varint_field(fn, v):
    return varint(fn << 3) + varint(v)


def pb_len_delimited(fn, data):
    tag = varint((fn << 3) | 2)
    return tag + varint(len(data)) + data


def build_subs(ssrc):
    inner = pb_varint_field(3, ssrc) + pb_varint_field(5, 0) + pb_varint_field(6, 0)
    return pb_len_delimited(1, inner)


def encode_attr(t, data):
    hdr = struct.pack("!HH", t, len(data))
    pad = (4 - (len(data) % 4)) % 4
    return hdr + data + b"\x00" * pad


def build_stun(username, key, subs):
    txid = os.urandom(12)
    attrs = bytearray()
    if username:
        attrs += encode_attr(ATTR_USERNAME, username)
    attrs += encode_attr(ATTR_PRIORITY, struct.pack("!I", 16777215))
    attrs += encode_attr(ATTR_ICE_CONTROLLING, os.urandom(8))
    if subs:
        attrs += encode_attr(ATTR_SENDER_SUBSCRIPTIONS, subs)

    mi_hdr = bytearray(20)
    mi_hdr[0:2] = struct.pack("!H", STUN_BINDING)
    mi_hdr[2:4] = struct.pack("!H", len(attrs) + 24)
    mi_hdr[4:8] = struct.pack("!I", STUN_MAGIC)
    mi_hdr[8:20] = txid
    mac = hmac.new(key, mi_hdr + bytes(attrs), hashlib.sha1).digest()
    attrs += encode_attr(ATTR_MESSAGE_INTEGRITY, mac)

    fp_hdr = bytearray(20)
    fp_hdr[0:2] = struct.pack("!H", STUN_BINDING)
    fp_hdr[2:4] = struct.pack("!H", len(attrs) + 8)
    fp_hdr[4:8] = struct.pack("!I", STUN_MAGIC)
    fp_hdr[8:20] = txid
    fp = crc32(fp_hdr + bytes(attrs)) ^ 0x5354554E
    attrs += encode_attr(ATTR_FINGERPRINT, struct.pack("!I", fp & 0xFFFFFFFF))

    hdr = bytearray(20)
    hdr[0:2] = struct.pack("!H", STUN_BINDING)
    hdr[2:4] = struct.pack("!H", len(attrs))
    hdr[4:8] = struct.pack("!I", STUN_MAGIC)
    hdr[8:20] = txid
    return bytes(hdr) + bytes(attrs)


def test(ip, port, token, key, timeout=10):
    print(f"Testing {ip}:{port} — DTLS first, then STUN ...")

    # Step 1: Send DTLS ClientHello
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)
    sock.connect((ip, port))

    ctx = SSL.Context(SSL.DTLS_CLIENT_METHOD)
    ctx.set_verify(SSL.VERIFY_NONE, lambda *a: True)
    dtls = SSL.Connection(ctx, sock)
    dtls.set_connect_state()

    print("  Step 1: Sending DTLS ClientHello ...")
    try:
        dtls.do_handshake()
    except SSL.WantReadError:
        print("    DTLS ClientHello sent (handshake in progress)")
    except Exception as e:
        print(f"    DTLS error: {e}")

    time.sleep(0.5)

    # Step 2: Send STUN over the same UDP socket (raw, not over DTLS)
    print("  Step 2: Sending STUN binding (raw UDP on same port) ...")
    subs = build_subs(0x12345678)
    local = "test"
    username = f"{token}:{local}".encode()
    hmac_key = key.encode() if isinstance(key, str) else key
    stun = build_stun(username, hmac_key, subs)

    # Send STUN raw (not over DTLS)
    sock.send(stun)
    print(f"    Sent {len(stun)} bytes STUN")

    try:
        data = sock.recv(4096)
        print(f"  Received: {len(data)} bytes")
        if data[0] & 0xC0 == 0:  # STUN packet
            mt = struct.unpack("!H", data[0:2])[0]
            print(f"  STUN response type: 0x{mt:04x}")
            if mt == 0x0101:
                print(f"  >>> SUCCESS: Relay responded to STUN after DTLS!")
        else:
            print(f"  Non-STUN response (likely DTLS): {data[:32].hex()}")
    except socket.timeout:
        print(f"  No response to STUN")

    sock.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ip")
    parser.add_argument("token")
    parser.add_argument("key")
    parser.add_argument("--port", type=int, default=3478)
    args = parser.parse_args()
    test(args.ip, args.port, args.token, args.key)


if __name__ == "__main__":
    main()
