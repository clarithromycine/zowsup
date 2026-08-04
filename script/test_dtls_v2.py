"""
DTLS test v2 — matches Go crypto/tls defaults more closely.
Forces DTLS 1.2, specific ciphers, no SNI.
"""
import argparse
import socket
import struct
import sys
import time
from OpenSSL import SSL

def test(ip, port, timeout=10):
    print(f"Testing DTLS v2 to {ip}:{port} ...")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.5)
    sock.connect((ip, port))

    ctx = SSL.Context(SSL.DTLS_CLIENT_METHOD)
    ctx.set_verify(SSL.VERIFY_NONE, lambda *a: True)

    # Force DTLS 1.2 only
    try:
        ctx.set_options(SSL.OP_NO_DTLSv1)
    except AttributeError:
        pass
    ctx.set_verify(SSL.VERIFY_NONE, lambda *a: True)

    # Match Go's cipher preferences: ECDHE first, GCM
    ctx.set_cipher_list(
        "ECDHE-ECDSA-AES128-GCM-SHA256:"
        "ECDHE-RSA-AES128-GCM-SHA256:"
        "ECDHE-ECDSA-AES256-GCM-SHA384"
    )

    dtls = SSL.Connection(ctx, sock)
    dtls.set_connect_state()

    try:
        start = time.time()
        while time.time() - start < timeout:
            try:
                dtls.do_handshake()
                elapsed = time.time() - start
                print(f"  DTLS handshake OK in {elapsed:.3f}s")
                break
            except SSL.WantReadError:
                pass
            except SSL.WantWriteError:
                pass
            except SSL.Error as e:
                print(f"  DTLS error: {e}")
                return False
            time.sleep(0.05)
        else:
            print(f"  DTLS timeout")
            return False

        dtls.shutdown()
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False
    finally:
        sock.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ip")
    parser.add_argument("--port", type=int, default=3478)
    args = parser.parse_args()
    ok = test(args.ip, args.port)
    print("OK" if ok else "FAIL")

if __name__ == "__main__":
    main()
