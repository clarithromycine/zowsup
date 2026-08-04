"""
Call key generation and per-JID SRTP key derivation for WhatsApp VoIP.

Flow:
  callKey (32 random bytes)
    └─► DerivePerJidSrtpKey(callKey, deviceJid)
          └─► HKDF-SHA256(IKM=callKey, salt="", info=deviceJid, length=46)
                ├─► [0:16]  → SrtpKeyingMaterial.master_key  (AES-128 key)
                └─► [16:30] → SrtpKeyingMaterial.master_salt (SRTP salt)

Each device gets a different key pair based on its JID, ensuring
per-device per-direction encryption.

Reference: WaCalls internal/voip/media/encryption.go
"""

import os
import hashlib
from dataclasses import dataclass


@dataclass
class SrtpKeyingMaterial:
    """SRTP master keying material for a single device/direction."""
    master_key: bytes   # 16 bytes — AES-128 encryption key
    master_salt: bytes  # 14 bytes — SRTP salt


def generate_call_key() -> bytes:
    """Generate a 32-byte random call key."""
    return os.urandom(32)


def derive_warp_auth_key(call_key: bytes) -> bytes:
    """
    Derive WARP message-integrity auth key from the call key.

    WACRG CRY-07 (warp-crypto):
        warp_auth_key = HKDF-SHA256(salt="", IKM=callKey, info="warp auth key", L=32)
    """
    return _hkdf_sha256(
        ikm=call_key,
        salt=b"",
        info=b"warp auth key",
        length=32,
    )


def derive_per_jid_srtp_key(call_key: bytes, device_jid: str) -> SrtpKeyingMaterial:
    """
    Derive per-JID SRTP master keying from the call key.

    WACRG CRY-05 (srtp-e2e):
        masterKey(16) || masterSalt(14) || unused(16)
            = HKDF-SHA256(salt=32 zero bytes, IKM=callKey, info=participantLID, L=46)

    Args:
        call_key: 32-byte call key
        device_jid: Participant LID string (UTF-8 bytes)
    """
    derived = _hkdf_sha256(
        ikm=call_key,
        salt=b"",
        info=device_jid.encode(),
        length=46,
    )
    return SrtpKeyingMaterial(
        master_key=derived[0:16],
        master_salt=derived[16:30],
    )


def _hkdf_sha256(ikm: bytes, salt: bytes, info: bytes, length: int) -> bytes:
    """HKDF-SHA256 key derivation."""
    try:
        return hashlib.hkdf_expand(ikm, salt=salt, info=info, length=length, digest=hashlib.sha256)
    except AttributeError:
        pass

    # Fallback for Python < 3.12
    import hmac
    # Extract
    prk = hmac.new(salt, ikm, hashlib.sha256).digest() if salt else hmac.new(
        b'\x00' * 32, ikm, hashlib.sha256
    ).digest() if salt == b"" else hmac.new(salt, ikm, hashlib.sha256).digest()

    # Expand
    result = b""
    t = b""
    i = 1
    while len(result) < length:
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        result += t
        i += 1
    return result[:length]


# ── SRTP AES-CTR decryption ──────────────────────────────────
# Matches WaCalls internal/voip/media/srtp.go exactly.

SRTP_LABEL_ENCRYPTION = 0x00
SRTP_LABEL_AUTH = 0x01
SRTP_LABEL_SALT = 0x02
SRTP_AUTH_TAG_LEN = 4


def _aes_ctr_xor(key: bytes, iv: bytes, data: bytes) -> bytes:
    """AES-CTR encrypt/decrypt (stream XOR, no padding). Uses pycryptodome."""
    from Crypto.Cipher import AES
    cipher = AES.new(key, AES.MODE_CTR, nonce=b'', initial_value=iv)
    return cipher.encrypt(data)


def _derive_srtp_subkey(master_key: bytes, master_salt: bytes, label: int, length: int) -> bytes:
    """Derive SRTP session key / auth key / salt via AES-CTR.
    Matches Go deriveSrtpKey()."""
    iv = bytearray(16)
    iv[:len(master_salt)] = master_salt[:14]
    iv[7] ^= label
    return _aes_ctr_xor(master_key, bytes(iv), b'\x00' * length)


def _generate_iv(session_salt: bytes, ssrc: int, packet_index: int) -> bytes:
    """Build SRTP AES-CTR IV. Matches Go generateIV()."""
    import struct
    iv = bytearray(16)
    iv[:14] = session_salt[:14]
    ssrc_bytes = struct.pack(">I", ssrc)
    for i in range(4):
        iv[4 + i] ^= ssrc_bytes[i]
    idx_bytes = struct.pack(">Q", packet_index)
    for i in range(6):
        iv[8 + i] ^= idx_bytes[2 + i]
    return bytes(iv)


class SrtpContext:
    """SRTP decrypt context for WhatsApp audio frames.
    Matches WaCalls SrtpContext / Unprotect."""

    def __init__(self, key_material: SrtpKeyingMaterial):
        self.session_key = _derive_srtp_subkey(
            key_material.master_key, key_material.master_salt,
            SRTP_LABEL_ENCRYPTION, 16)
        self.session_salt = _derive_srtp_subkey(
            key_material.master_key, key_material.master_salt,
            SRTP_LABEL_SALT, 14)
        self.auth_key = _derive_srtp_subkey(
            key_material.master_key, key_material.master_salt,
            SRTP_LABEL_AUTH, 20)
        self._roc = 0
        self._last_seq = 0
        self._initialized = False

    def decrypt(self, ssrc: int, seq: int, payload: bytes) -> bytes:
        """Decrypt an SRTP payload. Returns plaintext."""
        self._update_roc(seq)
        packet_index = (self._roc << 16) | seq
        iv = _generate_iv(self.session_salt, ssrc, packet_index)
        return _aes_ctr_xor(self.session_key, iv, payload)

    def _update_roc(self, seq: int):
        if not self._initialized:
            self._last_seq = seq
            self._initialized = True
            return
        diff = (seq - self._last_seq) & 0xFFFF
        if diff > 32768:  # seq wrapped around
            self._roc += 1
        self._last_seq = seq


# ── SFrame (AES-128-GCM) layer ───────────────────────────────
# WACRG: SFrame encrypts each media frame end-to-end INSIDE E2E SRTP.
# Key derivation is HKDF-SHA256 with split callKey as salt/IKM.
# Direction is OPPOSITE of E2E SRTP: sender uses peer's id, receiver uses self's id.


def derive_sframe_key(call_key: bytes, participant_id: str) -> bytes:
    """
    Derive per-participant SFrame key (32 bytes).

    WACRG spec:
      sframe_key = HKDF-SHA256(salt=callKey[0:16], ikm=callKey[16:32],
                               info="e2e sframe key" + participantID, L=32)
    Participant ID: bare @lid → user:0@lid
    """
    import hmac as _hmac
    # Format participant ID: bare @lid → :0@lid
    if participant_id.endswith("@lid") and ":" not in participant_id.split("@")[0]:
        participant_id = participant_id.split("@")[0] + ":0@lid"

    info = b"e2e sframe key" + participant_id.encode()
    # HKDF-Extract: PRK = HMAC-SHA256(key=salt, msg=IKM)
    prk = _hmac.new(call_key[0:16], call_key[16:32], hashlib.sha256).digest()
    # HKDF-Expand to 32 bytes
    okm = b""
    t = b""
    i = 1
    while len(okm) < 32:
        t = _hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        okm += t
        i += 1
    return okm[:32]


class SFrameContext:
    """AES-128-GCM SFrame encrypt/decrypt for one direction."""

    def __init__(self, key: bytes):
        if len(key) != 32:
            raise ValueError(f"SFrame key must be 32 bytes, got {len(key)}")
        # Use first 16 bytes as AES-128 key
        self._aes_key = key[:16]
        self._counter = 0

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt plaintext → [ciphertext || 16B GCM tag || varint header]."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(self._aes_key)
        nonce = self._build_nonce()
        ct = aesgcm.encrypt(nonce, plaintext, None)
        # Wire layout: ciphertext+tag (GCM output) + varint header
        header = self._varint_encode(self._counter)
        self._counter += 1
        return ct + header

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt [ciphertext || 16B GCM tag || varint header] → plaintext."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        if len(data) < 17:  # min: 1B ct + 16B tag
            raise ValueError("SFrame data too short")
        # Parse varint header from end
        ct_plus_tag, counter = self._parse_trailer(data)
        self._counter = counter + 1  # advance past this frame
        aesgcm = AESGCM(self._aes_key)
        nonce = self._build_nonce_for(counter)
        return aesgcm.decrypt(nonce, ct_plus_tag, None)

    def _build_nonce(self) -> bytes:
        return self._build_nonce_for(self._counter)

    def _build_nonce_for(self, counter: int) -> bytes:
        """16-byte nonce: 8 zero bytes || counter (LE u64)."""
        import struct
        return b'\x00' * 8 + struct.pack("<Q", counter & 0xFFFFFFFFFFFFFFFF)

    @staticmethod
    def _varint_encode(value: int) -> bytes:
        """Encode as unsigned varint."""
        result = []
        v = value & 0xFFFFFFFFFFFFFFFF
        while v > 0x7F:
            result.append((v & 0x7F) | 0x80)
            v >>= 7
        result.append(v & 0x7F)
        return bytes(result)

    @staticmethod
    def _parse_trailer(data: bytes):
        """Parse varint trailer from end of SFrame data."""
        # Scan backwards for varint (high bit set = continuation)
        header_start = len(data) - 1
        while header_start > 0 and (data[header_start - 1] & 0x80):
            header_start -= 1
        header_bytes = data[header_start:]
        counter = 0
        for i, b in enumerate(header_bytes):
            counter |= (b & 0x7F) << (7 * i)
        return data[:header_start], counter
