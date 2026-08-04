"""
QR pair-device encryption utilities.

Reverse-engineered from WhatsApp APK (classes9.dex):
  C40268Hr6.A05 — encrypt plaintext with server's encryption_pem certificate
  C40268Hr6.A01 — build password hash (encrypt advSecret with client's RSA pubkey)
  AbstractC40168HpI.A01 — derive secretKey via HKDF
  AbstractC40142Hor.A01/A02/A03 — RSA key generation & PEM serialization
"""

import hashlib
import hmac
import json
import os
import struct
import time
from base64 import b64encode
import base64

from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes

from common.utils import Utils

# ── Constants ────────────────────────────────────────────────────────
HKDF_INFO = b"Canonical Ent Companion Nonce Encrypt"
PASSWORD_PREFIX = "#PWD_WA:11"
AES_BLOCK_SIZE = 16
RSA_KEY_SIZE = 2048


# ── Step 1: secretKey derivation ─────────────────────────────────────
# APK IO1.A01:
#   SecretKeySpec(C1V0.A02(adv_secret, priorAttemptKey, IJW.A00, 32), "AES-GCM")
#   = HKDF(ikm=adv_secret, salt=priorAttemptKey_or_null, info=IJW.A00, L=32)
# For first pairing: priorAttemptKey = null → HKDF uses zero-byte salt.

def derive_secret_key(adv_secret: bytes, salt: bytes | None = None) -> bytes:
    """
    HKDF-SHA256(ikm=adv_secret, salt=priorAttemptKey, info="Canonical Ent Companion Nonce Encrypt", L=32)

    Args:
        adv_secret: 32-byte adv_secret from QR code (field 4)
        salt: priorAttemptKey (null for first pairing → zero-byte salt).
              Do NOT pass companion_noise_pub here — that was a bug.
    Returns:
        32-byte derived secretKey
    """
    return Utils.extract_and_expand(
        key=adv_secret,
        info=HKDF_INFO,
        output_length=32,
        salt=salt,
    )


# ── Step 2: RSA key generation ──────────────────────────────────────
# AbstractC40142Hor.A02() → KeyPair(RSA-2048)

def generate_rsa_keypair() -> RSA.RsaKey:
    """Generate RSA-2048 key pair."""
    return RSA.generate(RSA_KEY_SIZE)


def rsa_pubkey_to_pem(pubkey: RSA.RsaKey) -> str:
    """
    Serialize RSA public key to PEM format.
    AbstractC40142Hor.A01() → "-----BEGIN PUBLIC KEY-----\n{base64}\n-----END PUBLIC KEY-----\n"
    """
    der = pubkey.publickey().export_key(format="DER")
    b64 = b64encode(der).decode("ascii")
    return f"-----BEGIN PUBLIC KEY-----\n{b64}\n-----END PUBLIC KEY-----\n"


def rsa_pubkey_from_pem(pem_str: str) -> RSA.RsaKey:
    """Parse PEM-format RSA public key. (AbstractC40142Hor.A03)"""
    return RSA.import_key(pem_str)


# ── Step 3: Password hash ────────────────────────────────────────────
# C40268Hr6.A01(num, advSecret, aad=null, clientRSAPubKey)
#   → binary blob: [ver(1)] [key_type(1)] [nonce(12)]
#     [encKeyLen(2 LE)] [encKey(RSA/PKCS1)] [tag(16)] [ciphertext]
#   → wrapped as: "#PWD_WA:11:{timestamp}:{base64(blob)}"

def build_password_hash(
    adv_secret: bytes,
    key_type: int = 0,
    client_rsa_pubkey: RSA.RsaKey | None = None,
    timestamp: int = 0,
) -> str:
    """
    Build the password string for the plaintext JSON.

    Algorithm (from C40268Hr6.A01 rsa2048 path, confirmed AES-GCM):
      1. Generate random AES-256 key
      2. Generate random 12-byte nonce
      3. AES-GCM encrypt(adv_secret, aes_key, nonce) → ciphertext + 16-byte tag
      4. RSA/PKCS1 encrypt(aes_key, client_rsa_pubkey)
      5. Assemble binary blob: [1][key_type][nonce][encKeyLen(2 LE)][encKey][tag][ciphertext]
      6. Wrap as: "#PWD_WA:11:{timestamp}:{base64(blob)}"

    Returns:
        PWD_WA-formatted string with base64-encoded blob
    """
    if client_rsa_pubkey is None:
        raise ValueError("client_rsa_pubkey is required for password hash")

    aes_key = get_random_bytes(32)       # AES-256
    iv = get_random_bytes(12)            # 12-byte nonce for AES-GCM

    # AES-GCM encrypt (confirmed from real device trace analysis — 12-byte nonce + 16-byte tag)
    cipher = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
    ciphertext, auth_tag = cipher.encrypt_and_digest(adv_secret)

    # RSA/PKCS1 encrypt the AES key
    rsa_cipher = PKCS1_v1_5.new(client_rsa_pubkey)
    encrypted_key = rsa_cipher.encrypt(aes_key)

    # Build binary blob
    enc_key_len = len(encrypted_key)
    blob = bytearray()
    blob.append(1)                       # version
    blob.append(key_type & 0xFF)         # key_type
    blob.extend(iv)                      # 12-byte nonce
    blob.extend(struct.pack("<H", enc_key_len))  # encrypted key length (2 bytes LE)
    blob.extend(encrypted_key)           # RSA/PKCS1 encrypted AES key
    blob.extend(auth_tag)                # 16-byte GCM auth tag
    blob.extend(ciphertext)              # ciphertext (same length as plaintext)

    # Wrap as PWD_WA format with URL-safe base64 without padding (AZZ.A0w, flag=11)
    blob_b64 = base64.urlsafe_b64encode(bytes(blob)).decode().rstrip("=")
    return f"{PASSWORD_PREFIX}:{timestamp}:{blob_b64}"


# ── Step 4: Encryption-metadata (C40268Hr6.A05 rsa2048 path) ────────
# Encrypts plaintext with AES-GCM, then RSA-OAEP(SHA-1) wraps the AES key.

def encrypt_pair_device_metadata(
    plaintext_json: str,
    encryption_pem_cert_pem: str,
) -> tuple[bytes, bytes, bytes, bytes]:  # (encrypted_key, ciphertext, auth_tag, nonce)
    """
    Encrypt plaintext for the <encryption-metadata> field.

    Algorithm (confirmed AES-GCM from real device trace analysis):
      1. Generate random AES-256 key
      2. Generate random 12-byte nonce (AES-GCM standard nonce size)
      3. AES-GCM encrypt(plaintext_json, aes_key, nonce) → ciphertext + 16-byte tag
      4. RSA/OAEP(SHA-1) encrypt(aes_key, encryption_pem_pubkey)

    Evidence: real device ciphertext lengths are NOT multiples of 16
    (1035 bytes, 1047 bytes), which rules out AES-CBC and confirms AES-GCM.

    Args:
        plaintext_json: JSON string to encrypt
        encryption_pem_cert_pem: PEM-format X.509 certificate from WWWGetCertificates

    Returns:
        (encrypted_key, encrypted_data, auth_tag, nonce)
        Matches C9QB fields: A02=encKey, A01=encData, A00=authTag, A03=nonce
    """
    # Parse X.509 certificate to get RSA public key
    pem_str = encryption_pem_cert_pem.strip()

    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    try:
        cert_obj = x509.load_pem_x509_certificate(pem_str.encode(), default_backend())
        pubkey_der = cert_obj.public_key().public_bytes(
            Encoding.DER, PublicFormat.SubjectPublicKeyInfo
        )
        rsa_pubkey = RSA.import_key(pubkey_der)
    except Exception:
        # Fallback: try as raw public key PEM
        try:
            rsa_pubkey = RSA.import_key(pem_str)
        except Exception as e:
            raise ValueError(f"Failed to parse encryption certificate: {e}") from e

    aes_key = get_random_bytes(32)       # AES-256
    nonce = get_random_bytes(12)         # 12-byte nonce for AES-GCM

    # AES-GCM encrypt (no padding needed, ciphertext = plaintext length)
    plaintext_bytes = plaintext_json.encode("utf-8")
    cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
    ciphertext, auth_tag = cipher.encrypt_and_digest(plaintext_bytes)

    # RSA-OAEP(SHA-1) wrap the AES key
    from Crypto.Cipher import PKCS1_OAEP
    from Crypto.Hash import SHA1

    rsa_cipher = PKCS1_OAEP.new(rsa_pubkey, hashAlgo=SHA1)
    encrypted_key = rsa_cipher.encrypt(aes_key)

    return encrypted_key, ciphertext, auth_tag, nonce


# ── Step 5: Build plaintext JSON ─────────────────────────────────────

def build_pair_device_plaintext(
    timestamp: int,
    password_hash: str,
    client_pub_key_pem: str
) -> str:
    """
    Build the plaintext JSON that gets encrypted into <encryption-metadata>.

    Format (confirmed from real device trace size analysis — 1035 bytes):
      {"version":"...", "timestamp":..., "password":"#PWD_WA:11:{ts}:{base64_blob}",
       "client_pub_key":"...", "client_pub_key_type":"RSA 2048"}

    The password field uses the PWD_WA prefix format with base64-encoded blob
    (not hex), and includes a 'did' field with the device ID as string.
    """
    data = {
        "version": 1,
        "timestamp": timestamp,
        "password": password_hash,
        "client_pub_key": client_pub_key_pem,
        "client_pub_key_type": "RSA 2048",
    }
    return json.dumps(data, separators=(",", ":"))
