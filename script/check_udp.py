"""
Quick UDP connectivity check — tests whether relay port 3478 receives packets.

Sends a raw UDP packet and waits for any response.
If the relay port is open, it should at least not return ICMP unreachable.

Usage:
    python script/check_udp.py <relay_ip> [--port 3478]
"""

import argparse
import socket
import sys
import time


def check_udp(ip: str, port: int, timeout: float = 3.0):
    print(f"Testing UDP to {ip}:{port} ...")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)

    # Send a simple UDP packet
    payload = b"\x00" * 20
    sock.sendto(payload, (ip, port))
    print(f"  Sent {len(payload)} bytes to {ip}:{port}")

    start = time.time()
    try:
        data, addr = sock.recvfrom(4096)
        elapsed = time.time() - start
        print(f"  Received {len(data)} bytes from {addr} in {elapsed*1000:.0f}ms")
        print(f"  First 32 bytes: {data[:32].hex()}")
        print(f"  RESULT: PORT OPEN (got response)")
    except socket.timeout:
        elapsed = time.time() - start
        print(f"  No response after {elapsed:.1f}s")
        print(f"  RESULT: NO RESPONSE (no ICMP reject either — port may be firewalled or silently dropping)")
    except ConnectionResetError:
        print(f"  RESULT: ICMP PORT UNREACHABLE — port is CLOSED")
    except Exception as e:
        print(f"  RESULT: ERROR — {e}")
    finally:
        sock.close()


def main():
    parser = argparse.ArgumentParser(description="Raw UDP connectivity test")
    parser.add_argument("ip", help="Relay IP address")
    parser.add_argument("--port", type=int, default=3478)
    args = parser.parse_args()
    check_udp(args.ip, args.port)


if __name__ == "__main__":
    main()
