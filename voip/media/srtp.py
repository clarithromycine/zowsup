"""
SRTP (Secure RTP) — AES-128-CTR encryption + HMAC-SHA1 authentication.

Implements SRTP protect/unprotect for WhatsApp VoIP media packets.
- Cipher: AES-128-CTR
- Auth: HMAC-SHA1, 4-byte auth tag
- Key derivation: HKDF-SHA256 with SRTP labels

Reference: WaCalls internal/voip/media/srtp.go
"""

import hashlib
import hmac
import struct
from Crypto.Cipher import AES

from .rtp import RtpPacket, RtpHeader


# SRTP auth tag length (WhatsApp uses 4 bytes)
SRTP_AUTH_TAG_LEN = 4

# SRTP key derivation labels
SRTP_LABEL_ENCRYPTION = 0x00  # → session_key (16 bytes)
SRTP_LABEL_AUTH = 0x01        # → auth_key (20 bytes)
SRTP_LABEL_SALT = 0x02        # → session_salt (14 bytes)


class SrtpError(Exception):
    """SRTP processing error."""
    pass


class SrtpContext:
    """
    SRTP encryption/decryption context for a single SSRC stream.

    Each direction (send/recv) has its own SrtpContext with different
    master keys (derived per-JID from the call key).
    """

    def __init__(self, master_key: bytes, master_salt: bytes, auth_tag_len: int = SRTP_AUTH_TAG_LEN,
                 hbh: bool = False, _skip_kdf: bool = False, warp_auth_key: bytes = None):
        if len(master_key) != 16:
            raise ValueError(f"Master key must be 16 bytes, got {len(master_key)}")
        if len(master_salt) != 14:
            raise ValueError(f"Master salt must be 14 bytes, got {len(master_salt)}")

        self.master_key = master_key
        self.master_salt = master_salt
        self.auth_tag_len = auth_tag_len
        self._hbh = hbh  # True → HBH IV (packetIndex << 16); False → E2E IV
        self._warp_auth_key = warp_auth_key  # WARP MI tag key (separate from SRTP auth_key!)

        if _skip_kdf:
            # Use master_key/master_salt directly as session keys (no RFC 3711 KDF)
            self.session_key = master_key
            self.auth_key = b'\x00' * 20  # unused for raw mode
            self.session_salt = master_salt
        else:
            # Derived keys via RFC 3711 KDF
            self.session_key = _derive_srtp_key(master_key, master_salt, SRTP_LABEL_ENCRYPTION, 16)
            self.auth_key = _derive_srtp_key(master_key, master_salt, SRTP_LABEL_AUTH, 20)
            self.session_salt = _derive_srtp_key(master_key, master_salt, SRTP_LABEL_SALT, 14)

        # Pre-keyed AES-CTR: key schedule computed ONCE here, reused for all packets
        self._fast_ctr = _FastAesCtr(self.session_key)

        # ROC (Rollover Counter)
        self.roc: int = 0
        self._last_seq: int = 0
        self._initialized: bool = False

    def protect_payload_only(self, payload: bytes, ssrc: int, seq: int) -> bytes:
        """
        Encrypt Opus payload only → encrypted bytes (NO auth tag).

        WACRG REL-07: MI tag covers header || encrypted. Caller must compute MI.
        """
        self._update_roc(seq)
        index = self._packet_index(seq)
        iv = self._generate_iv(ssrc, index)
        return self._fast_ctr.crypt(iv, payload)

    def compute_warp_mi(self, data: bytes) -> bytes:
        """
        WARP MESSAGE-INTEGRITY tag over packet bytes + ROC.

        Uses auth_key (RFC 3711 KDF label 0x01) — NOT warp_auth_key.
        Reverting to warp_auth_key causes reconnecting, so auth_key is correct.
        """
        import hmac as _hmac
        import hashlib as _hashlib
        mac = _hmac.new(self.auth_key, digestmod=_hashlib.sha1)
        mac.update(data)
        mac.update(struct.pack("!I", self.roc))
        return mac.digest()[:self.auth_tag_len]

    def protect(self, packet: RtpPacket) -> bytes:
        """
        Encrypt an RTP packet → SRTP bytes (header + encrypted_payload + auth_tag).
        """
        header = packet.header
        self._update_roc(header.sequence_number)
        index = self._packet_index(header.sequence_number)

        header_bytes = header.encode()
        header_size = len(header_bytes)

        # Output: header + encrypted_payload + auth_tag
        output = bytearray(header_size + len(packet.payload) + self.auth_tag_len)
        output[:header_size] = header_bytes

        # AES-CTR encrypt payload
        iv = self._generate_iv(header.ssrc, index)
        encrypted = self._fast_ctr.crypt(iv, packet.payload)
        output[header_size:header_size + len(encrypted)] = encrypted

        # HMAC-SHA1 auth tag
        if self.auth_tag_len > 0:
            auth_data = bytes(output[:header_size + len(packet.payload)])
            tag = self._compute_auth_tag(auth_data)
            output[header_size + len(packet.payload):] = tag[:self.auth_tag_len]

        return bytes(output)

    def decrypt_payload_only(self, data: bytes, ssrc: int, seq: int, auth_tag_len: int = 4) -> bytes:
        """
        Decrypt E2E-SRTP payload from WARP frame (header plaintext, payload encrypted).

        WACRG REL-07 inbound loop:
          1. Strip trailing WARP MI tag (4B)
          2. Parse plaintext RTP header → SSRC, seq
          3. AES-CTR decrypt remaining bytes (= encrypted Opus)

        Returns: decrypted Opus payload bytes
        """
        if len(data) <= auth_tag_len:
            raise SrtpError(f"Data too short: {len(data)}B (need >{auth_tag_len}B for MI tag)")
        
        # Strip MI tag
        payload_data = data[:-auth_tag_len]
        
        # Parse RTP header to get SSRC and seq from plaintext
        header = RtpHeader.decode(payload_data)
        header_size = header.size()
        
        # Extract encrypted payload (bytes after header, before MI tag)
        encrypted = payload_data[header_size:]
        if len(encrypted) == 0:
            return b""
        
        # Use the header's SSRC and seq for IV generation
        self._update_roc(header.sequence_number)
        index = self._packet_index(header.sequence_number)
        iv = self._generate_iv(header.ssrc, index)
        
        # Decrypt
        return self._fast_ctr.crypt(iv, encrypted)
    def unprotect(self, data: bytes) -> RtpPacket:
        """
        Decrypt and verify an SRTP packet → RtpPacket.

        Raises SrtpError on auth failure or malformed data.
        """
        if len(data) < 12:
            raise SrtpError(f"Packet too short: {len(data)} bytes")

        header = RtpHeader.decode(data)
        header_size = header.size()

        payload_len = len(data) - header_size - self.auth_tag_len
        if payload_len <= 0:
            raise SrtpError(f"No payload: {len(data)}B total, {header_size}B header, auth={self.auth_tag_len}")

        self._update_roc(header.sequence_number)
        index = self._packet_index(header.sequence_number)

        iv = self._generate_iv(header.ssrc, index)

        # Decrypt payload
        encrypted_payload = data[header_size:header_size + payload_len]
        decrypted = self._fast_ctr.crypt(iv, encrypted_payload)

        return RtpPacket(header=header, payload=decrypted)

    def decrypt_raw(self, data: bytes, ssrc: int, seq: int) -> RtpPacket:
        """
        Decrypt an SRTP blob where the RTP header is *also* encrypted.

        WhatsApp primary‑device relay frames (0x8FCE) carry a fully
        AES‑CTR‑encrypted SRTP packet — header + payload.  Standard
        unprotect() fails because it tries to read the (encrypted)
        RTP header for IV generation.

        Here the caller supplies *ssrc* and *seq* from the outer
        frame header, we generate the IV from those, decrypt the
        entire blob, and then parse the RtpPacket from the plaintext.
        """
        if len(data) < 12:
            raise SrtpError(f"Packet too short for raw decrypt: {len(data)} bytes")

        self._update_roc(seq)
        index = self._packet_index(seq)
        iv = self._generate_iv(ssrc, index)

        # Decrypt the entire blob (RTP header + payload)
        plain = self._fast_ctr.crypt(iv, data)

        import logging
        _log = logging.getLogger(__name__)
        _log.debug("decrypt_raw: plain[0:32]=%s", plain[:32].hex())

        # Parse RTP header from plaintext
        header = RtpHeader.decode(plain)
        header_size = header.size()

        # The rest is the Opus payload (auth tag already stripped by caller / relay)
        payload = plain[header_size:]

        return RtpPacket(header=header, payload=payload)
        """
        Verify the auth tag on an SRTP packet. Returns True if valid.
        """
        if self.auth_tag_len == 0:
            return True

        header = RtpHeader.decode(data)
        header_size = header.size()
        payload_len = len(data) - header_size - self.auth_tag_len
        if payload_len <= 0:
            return False

        auth_data = data[:header_size + payload_len]
        expected_tag = data[header_size + payload_len:header_size + payload_len + self.auth_tag_len]

        tag = self._compute_auth_tag(auth_data)[:self.auth_tag_len]
        return hmac.compare_digest(tag, expected_tag)

    # ── Internal ───────────────────────────────────────────────

    def _update_roc(self, seq: int):
        """Update ROC counter when sequence number wraps (matching Go int32 diff)."""
        if not self._initialized:
            self._last_seq = seq
            self._initialized = True
            return
        # Signed 32-bit difference (matching Go: int32(seq) - int32(lastSeq))
        raw_diff = seq - self._last_seq
        # Wrap to signed 32-bit range
        diff = (raw_diff + 2**31) % (2**32) - 2**31
        if diff < -32768:
            self.roc += 1
        self._last_seq = seq

    def _packet_index(self, seq: int) -> int:
        """SRTP packet index = (ROC << 16) | seq."""
        return (self.roc << 16) | (seq & 0xFFFF)

    def _generate_iv(self, ssrc: int, index: int) -> bytes:
        """
        SRTP IV construction — matches Go wacalls generateIV().

        Salt is LEFT-aligned at iv[0:14].
        E2E:  iv[0:14]=salt, iv[4:8]^=ssrc, iv[8:14]^=packetIndex(48-bit BE)
        HBH:  iv[0:14]=salt, iv[4:8]^=ssrc, iv[8:16]^=packetIndex<<16 (64-bit BE)
        """
        iv = bytearray(16)
        # Salt LEFT-aligned at bytes 0-14 (matching Go wacalls)
        iv[0:14] = self.session_salt[:14]

        # SSRC at bytes 4-8
        ssrc_bytes = struct.pack("!I", ssrc & 0xFFFFFFFF)
        for i in range(4):
            iv[4 + i] ^= ssrc_bytes[i]

        if self._hbh:
            # HBH: packetIndex << 16 → 8 bytes at iv[8:16]
            shifted = (index & 0xFFFFFFFFFFFF) << 16
            idx_bytes = struct.pack("!Q", shifted)
            for i in range(8):
                iv[8 + i] ^= idx_bytes[i]
        else:
            # E2E: 48-bit packetIndex at iv[8:14] (bytes 2-7 of uint64 BE)
            idx_bytes = struct.pack("!Q", index & 0xFFFFFFFFFFFF)[2:8]
            for i in range(6):
                iv[8 + i] ^= idx_bytes[i]

        return bytes(iv)

    def _compute_auth_tag(self, data: bytes) -> bytes:
        """
        Compute HMAC-SHA1 auth tag over the packet data + ROC.

        HMAC(auth_key, data + ROC_be)
        """
        mac = hmac.new(self.auth_key, digestmod=hashlib.sha1)
        mac.update(data)
        mac.update(struct.pack("!I", self.roc))
        return mac.digest()


# ── Internal helpers ──────────────────────────────────────────


def _derive_srtp_key(master_key: bytes, master_salt: bytes, label: int, length: int) -> bytes:
    """
    Derive an SRTP sub-key using AES-CTR (RFC 3711 §4.3).

    WACRG spec (confirmed):
        iv = masterSalt (14 bytes), zero-padded to 16
        iv[7] ^= label
        return AES-128-CM(masterKey, iv)[:L]
    """
    iv = bytearray(16)
    iv[:14] = master_salt[:14]
    iv[7] ^= (label & 0xFF)
    return _aes_ctr_encrypt(master_key, bytes(iv), b'\x00' * length)


class _FastAesCtr:
    """Pre-keyed AES-128-CTR: key schedule done ONCE at init, per-packet crypt is ECB-only.

    Avoids per-packet AES key expansion (~40% of AES cost for short frames).
    CTR is implemented manually over a pre-created ECB encryptor for maximum throughput.
    """
    __slots__ = ('_ecb',)

    def __init__(self, key: bytes):
        self._ecb = AES.new(key, AES.MODE_ECB)

    def crypt(self, iv: bytes, data: bytes) -> bytes:
        """CTR encrypt/decrypt (symmetric). iv=16B counter start; data ≤ ~200B for audio."""
        n = len(data)
        result = bytearray(n)
        ctr = int.from_bytes(iv, 'big')
        mask = (1 << 128) - 1
        for i in range(0, n, 16):
            keystream = self._ecb.encrypt(ctr.to_bytes(16, 'big'))
            chunk = data[i:i + 16]
            for j in range(len(chunk)):
                result[i + j] = chunk[j] ^ keystream[j]
            ctr = (ctr + 1) & mask
        return bytes(result)


def _aes_ctr_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    """AES-128-CTR encrypt/decrypt (symmetric) — fallback when no pre-keyed context."""
    return _FastAesCtr(key).crypt(iv, plaintext)
