"""
SFrame end-to-end media encryption (AES-128-GCM) over the relay.

Matches Rust whatsapp-rust sframe.rs:
  - Wire layout: [ciphertext || 16-byte tag || varint-header] (trailing header)
  - GCM nonce: 8 zero bytes || counter as u64 LITTLE-endian
  - Direction: encrypt_key = derive(callKey, PEER_JID)
               decrypt_key = derive(callKey, SELF_JID)
  - HKDF-SHA256(salt=callKey[0:16], ikm=callKey[16:32], info="e2e sframe key"+id, L=32)

Reference: whatsapp-rust wacore/src/voip/sframe.rs
"""

import hashlib
import hmac
import struct
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

GCM_TAG_LEN = 16


def _hkdf_sha256(ikm, salt, info, length):
    """HKDF-SHA256: salt=None → 32 zero bytes."""
    if len(salt) == 0:
        salt = b'\x00' * 32
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    result, t, i = b"", b"", 1
    while len(result) < length:
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        result += t; i += 1
    return result[:length]


def _format_participant_id(jid: str) -> str:
    """Bare @lid → :0@lid (same as ensureDeviceJid)."""
    if ":" in jid:
        at = jid.find("@")
        colon = jid.find(":")
        if at > colon:
            return jid
    return jid.replace("@", ":0@", 1)


def derive_sframe_key(call_key: bytes, participant_id: str) -> bytes:
    """
    Per-participant SFrame key (32 bytes, we use first 16 for AES-128-GCM).

    Rust: HKDF-SHA256(salt=callKey[0:16], ikm=callKey[16:32],
                      info="e2e sframe key" + participant_id, L=32)
    """
    pid = _format_participant_id(participant_id)
    info = b"e2e sframe key" + pid.encode()
    return _hkdf_sha256(call_key[16:32], call_key[0:16], info, 32)


def _decode_varint(data: bytes, offset: int) -> tuple:
    """Decode a varint. Returns (value, next_offset) or (None, offset)."""
    value, shift, i = 0, 0, offset
    while i < len(data):
        b = data[i]; i += 1
        value |= (b & 0x7F) << shift
        if b & 0x80 == 0:
            return value, i
        shift += 7
        if shift > 63:
            return None, i
    return None, i


def _encode_varint(value: int) -> bytes:
    """Encode a u64 as varint."""
    if value == 0:
        return b'\x00'
    out = bytearray()
    while value > 0:
        b = value & 0x7F
        value >>= 7
        if value > 0:
            b |= 0x80
        out.append(b)
    return bytes(out)


def _counter_to_iv(counter: int) -> bytes:
    """GCM nonce: 8 zero bytes || counter as LE u64."""
    return b'\x00' * 8 + struct.pack("<Q", counter)


def _build_sframe_header(counter: int, key_id: int) -> bytes:
    """Build trailing SFrame header: counter(varint) + key_id(varint) + total_len(1B)."""
    ctr_bytes = _encode_varint(counter)
    kid_bytes = _encode_varint(key_id)
    body = ctr_bytes + kid_bytes
    return body + bytes([len(body) + 1])


def _parse_sframe_header(header: bytes):
    """Parse trailing SFrame header. Returns (counter, key_id) or (None, None)."""
    if len(header) < 2:
        return None, None
    total_len = header[-1]
    if total_len != len(header):
        return None, None
    body = header[:-1]
    counter, next_off = _decode_varint(body, 0)
    if counter is None:
        return None, None
    key_id, _ = _decode_varint(body, next_off)
    return counter, key_id


class SframeSession:
    """SFrame send/recv with per-direction keys."""

    def __init__(self, call_key: bytes, self_jid: str, peer_jid: str):
        encrypt_key32 = derive_sframe_key(call_key, peer_jid)   # encrypt for peer
        decrypt_key32 = derive_sframe_key(call_key, self_jid)   # decrypt from peer
        self.encrypt_key = encrypt_key32[:16]
        self.decrypt_key = decrypt_key32[:16]
        self.tx_counter = 0

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt: [ciphertext || tag || varint-header]."""
        counter = self.tx_counter
        self.tx_counter += 1
        header = _build_sframe_header(counter, 0)
        nonce = _counter_to_iv(counter)
        aesgcm = AESGCM(self.encrypt_key)
        encrypted = aesgcm.encrypt(nonce, plaintext, None)
        return encrypted + header

    def decrypt(self, frame: bytes):
        """
        Decrypt one frame.
        Returns: ("decrypted", plaintext) or ("plaintext", raw_bytes) if not SFrame.
        """
        if len(frame) < GCM_TAG_LEN + 3:
            return "plaintext", frame

        header_len = frame[-1]
        if header_len < 3 or header_len > len(frame):
            return "plaintext", frame

        header_start = len(frame) - header_len
        header = frame[header_start:]
        ciphertext_with_tag = frame[:header_start]

        if len(ciphertext_with_tag) < GCM_TAG_LEN + 1:
            return "plaintext", frame

        counter, key_id = _parse_sframe_header(header)
        if counter is None:
            return "plaintext", frame

        nonce = _counter_to_iv(counter)
        try:
            aesgcm = AESGCM(self.decrypt_key)
            plain = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
            return "decrypted", plain
        except Exception:
            return "plaintext", frame
