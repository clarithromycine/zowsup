"""
SSRC derivation for WhatsApp VoIP.

WhatsApp derives SSRCs deterministically from the call ID and device JID
using HKDF-SHA256. This ensures both sides compute the same SSRCs without
exchanging them in-band.

SSRC = HKDF-SHA256(IKM=callID, salt=counter_le, info=deviceJid, length=4)
      → uint32 (little-endian)

Reference: WaCalls internal/voip/media/ssrc.go
"""

import hashlib
import struct


def generate_secure_ssrc(call_id: str, device_jid: str, counter: int = 0) -> int:
    """
    Generate a deterministic SSRC for a device in a call.

    Args:
        call_id: WhatsApp call ID (hex string)
        device_jid: Device JID (e.g. "1234567890:0@s.whatsapp.net")
        counter: SSRC counter (0 = primary audio, increments for additional streams)

    Returns:
        32-bit unsigned integer SSRC
    """
    salt = struct.pack("<I", counter)  # little-endian

    # HKDF-SHA256(IKM=callID, salt=counter_le, info=deviceJid, length=4)
    derived = _hkdf_sha256_expand(
        ikm=call_id.encode(),
        salt=salt,
        info=device_jid.encode(),
        length=4,
    )
    return struct.unpack("<I", derived)[0]  # little-endian uint32


def _hkdf_sha256_expand(ikm: bytes, salt: bytes, info: bytes, length: int) -> bytes:
    """
    HKDF-SHA256 expand using hashlib.

    Python 3.12+ has hkdf_expand in hashlib. Fallback to manual HMAC-based.
    """
    try:
        # Python 3.12+
        return hashlib.hkdf_expand(ikm, salt=salt, info=info, length=length, digest=hashlib.sha256)
    except AttributeError:
        pass

    # Fallback: manual HKDF using HMAC-SHA256
    # HKDF-Extract: PRK = HMAC-SHA256(salt, IKM)
    prk = _hmac_sha256(salt, ikm)

    # HKDF-Expand: T(1) || T(2) || ...
    result = b""
    t = b""
    i = 1
    while len(result) < length:
        t = _hmac_sha256(prk, t + info + bytes([i]))
        result += t
        i += 1

    return result[:length]


def _hmac_sha256(key: bytes, data: bytes) -> bytes:
    """HMAC-SHA256 helper."""
    import hmac
    return hmac.new(key, data, hashlib.sha256).digest()
