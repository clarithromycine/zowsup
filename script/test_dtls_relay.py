"""
Quick DTLS connectivity test — uses pyOpenSSL (already a project dependency).

Tests whether a WhatsApp relay endpoint on port 3478 accepts raw DTLS.

Usage:
    python script/test_dtls_relay.py <relay_ip> [--port 3478]
"""

import argparse
import hashlib
import socket
import struct
import sys
import time

from OpenSSL import SSL

WA_DTLS_FINGERPRINT = (
    "F9:CA:0C:98:A3:CC:71:D6:42:CE:5A:E2:53:D2:15:20:"
    "D3:1B:BA:D8:57:A4:F0:AF:BE:0B:FB:F3:6B:0C:A0:68"
)


def test_raw_dtls(ip: str, port: int, timeout: float = 10.0) -> bool:
    print(f"Testing DTLS to {ip}:{port} ...")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.5)
    sock.connect((ip, port))

    ctx = SSL.Context(SSL.DTLS_CLIENT_METHOD)
    ctx.set_verify(SSL.VERIFY_NONE, lambda *args: True)

    dtls_conn = SSL.Connection(ctx, sock)
    dtls_conn.set_connect_state()

    try:
        start = time.time()
        while time.time() - start < timeout:
            try:
                dtls_conn.do_handshake()
                elapsed = time.time() - start
                print(f"  DTLS handshake OK in {elapsed:.3f}s")
                break
            except SSL.WantReadError:
                pass
            except SSL.WantWriteError:
                pass
            except SSL.Error as e:
                print(f"  X DTLS error: {e}")
                return False
            time.sleep(0.05)
        else:
            print(f"  X DTLS timeout - relay does not respond to DTLS ClientHello")
            return False

        # Verify certificate fingerprint
        cert = dtls_conn.get_peer_certificate()
        if cert:
            der_bytes = cert.to_cryptography().public_bytes(
                cert.to_cryptography().public_bytes_encoding
            )
            print("Need to fix cert extraction")
        else:
            print(f"  ! No server certificate")

        # Send a WhatsApp relay framed test message
        frame_type = 0x02
        test_payload = b"\x00" * 4
        frame = struct.pack(">BH", frame_type, len(test_payload)) + test_payload
        try:
            dtls_conn.send(frame)
            print(f"  Sent test frame: {len(frame)} bytes")
        except SSL.WantWriteError:
            pass

        try:
            data = dtls_conn.recv(4096)
            print(f"  Received: {len(data)} bytes -> OK! Relay responded after DTLS!")
        except SSL.WantReadError:
            print(f"  ! No immediate response (may need proper STUN registration)")
        except Exception as e:
            print(f"  ! Recv error: {e}")

        dtls_conn.shutdown()
        return True

    except Exception as e:
        print(f"  X Unexpected: {e}")
        return False
    finally:
        try:
            sock.close()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Test raw DTLS to WhatsApp relay")
    parser.add_argument("ip", help="Relay IP address")
    parser.add_argument("--port", type=int, default=3478)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    result = test_raw_dtls(args.ip, args.port, args.timeout)
    print("\n  Raw DTLS WORKS" if result else "\n  Raw DTLS FAILS")
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
