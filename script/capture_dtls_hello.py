"""Capture pyOpenSSL DTLS ClientHello raw bytes for comparison with pion."""
import sys
import socket
from OpenSSL import SSL


class _CaptureSocket:
    """Wrapper around UDP socket that captures the first send()."""
    def __init__(self, sock):
        self._sock = sock
        self.captured = None

    def send(self, data, *args, **kwargs):
        # Rewrite DTLS 1.0 record layer → 1.2
        if len(data) >= 3 and data[0] == 0x16 and data[1:3] == b'\xfe\xff':
            data = b'\x16\xfe\xfd' + data[3:]
        if self.captured is None:
            self.captured = bytes(data)
            print(f"Captured {len(data)} bytes from ClientHello", flush=True)
        return self._sock.send(data, *args, **kwargs)

    def recv(self, *args, **kwargs):
        return self._sock.recv(*args, **kwargs)

    def settimeout(self, *args, **kwargs):
        return self._sock.settimeout(*args, **kwargs)

    def getsockname(self, *args, **kwargs):
        return self._sock.getsockname(*args, **kwargs)

    def fileno(self, *args, **kwargs):
        return self._sock.fileno(*args, **kwargs)


RELAY_IP = sys.argv[1] if len(sys.argv) > 1 else "57.144.203.54"
RELAY_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 3478

raw = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
raw.settimeout(3)
raw.connect((RELAY_IP, RELAY_PORT))
sock = _CaptureSocket(raw)

ctx = SSL.Context(SSL.DTLS_CLIENT_METHOD)
ctx.set_options(SSL.OP_NO_TLSv1 | SSL.OP_NO_TLSv1_1)  # Force DTLS 1.2
ctx.set_cipher_list(b"ECDHE-ECDSA-AES128-GCM-SHA256")
ctx.set_verify(SSL.VERIFY_NONE, lambda *a: True)

conn = SSL.Connection(ctx, sock)
conn.set_connect_state()

try:
    conn.do_handshake()
    print("DTLS handshake OK")
    conn.shutdown()
except Exception as e:
    print(f"DTLS handshake FAIL: {e}")

if sock.captured:
    data = sock.captured
    print(f"\n--- ClientHello ({len(data)} bytes) ---")
    for i in range(0, len(data), 16):
        hex_str = " ".join(f"{b:02x}" for b in data[i : i + 16])
        ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in data[i : i + 16])
        print(f"{i:04x}  {hex_str:<48s} |{ascii_str}|")
else:
    print("\nNo ClientHello captured")

raw.close()
