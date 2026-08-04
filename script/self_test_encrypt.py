"""Self-test: generate cert, encrypt with our code, decrypt, verify round-trip.

This eliminates ALL external dependencies (server, network, GetCertificates).
If this passes, our crypto is correct and the issue is elsewhere.
If this fails, we found the bug.
"""

import json
from datetime import datetime
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa as crypto_rsa
from cryptography.x509 import (
    CertificateBuilder, Name, NameAttribute, BasicConstraints, random_serial_number,
)
import datetime as dt
import os, sys

# Add project path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.layer.canonical_credentials import (
    _rand_pwd, _jj5_a01, build_pwd_wa_hash, encrypt_with_cert, decrypt_response,
)

# ── Step 1: Generate self-signed X509 cert ──
print("=== Step 1: Generate self-signed cert ===")
from cryptography.x509 import (
    CertificateBuilder, Name, NameAttribute, BasicConstraints, random_serial_number,
)
import datetime as dt

# Generate cert using cryptography (needed for signing)
crypto_key = crypto_rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
crypto_pub = crypto_key.public_key()

# Also create PyCryptodome RSA key for our functions
# Export private key from cryptography, import to PyCryptodome
der_pub = crypto_pub.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
private_key = RSA.import_key(crypto_key.private_bytes(
    serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
))
public_key = private_key.publickey()

subject = issuer = Name([
    NameAttribute(NameOID.COUNTRY_NAME, "US"),
    NameAttribute(NameOID.ORGANIZATION_NAME, "Test"),
    NameAttribute(NameOID.COMMON_NAME, "test.local"),
])

cert_builder = CertificateBuilder().subject_name(subject).issuer_name(issuer)
cert_builder = cert_builder.public_key(crypto_pub)
cert_builder = cert_builder.serial_number(random_serial_number())
cert_builder = cert_builder.not_valid_before(dt.datetime.now(dt.timezone.utc))
cert_builder = cert_builder.not_valid_after(
    dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)
)
cert_builder = cert_builder.add_extension(
    BasicConstraints(ca=False, path_length=None), critical=True,
)

cert = cert_builder.sign(private_key=crypto_key, algorithm=hashes.SHA256(), backend=default_backend())
cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
print(f"Cert PEM: {len(cert_pem)} chars")
print(f"Cert first 80: {cert_pem[:80]}")

# ── Step 2: Build inner plaintext (same as Exchange flow) ──
print("\n=== Step 2: Build inner plaintext ===")
password = _rand_pwd()
ts = int(datetime.now().timestamp())
pub_pem = _jj5_a01(public_key)

# Use cert_pem as BOTH encryption cert and password public key (self-test)
pwd_hash = build_pwd_wa_hash(password, key_id=1, pubkey_pem=pub_pem, timestamp=ts)

plaintext = json.dumps({
    "version": 1,
    "timestamp": ts,
    "password": pwd_hash,
    "client_pub_key": pub_pem,
    "client_pub_key_type": "RSA 2048",
}, separators=(",", ":"))

print(f"Plaintext: {len(plaintext)} bytes")
print(f"Password:  {password}")
print(f"PWD_WA:    {pwd_hash[:60]}...")

# ── Step 3: Encrypt with our encrypt_with_cert ──
print("\n=== Step 3: Encrypt ===")
enc_key, ctxt, tag, iv = encrypt_with_cert(plaintext, cert_pem)
print(f"enc_key: {len(enc_key)}B  (expect 256)")
print(f"ctxt:    {len(ctxt)}B   (should match plaintext {len(plaintext)})")
print(f"tag:     {len(tag)}B    (expect 16)")
print(f"iv:      {len(iv)}B     (expect 12)")

if len(enc_key) != 256:
    print("FAIL: enc_key size wrong!")
    sys.exit(1)
if len(ctxt) != len(plaintext):
    print("FAIL: ciphertext size != plaintext size!")
    sys.exit(1)

# ── Step 4: Decrypt with our decrypt_response ──
print("\n=== Step 4: Decrypt ===")
try:
    decrypted = decrypt_response(enc_key, ctxt, tag, iv, private_key)
    print(f"Decrypted: {len(decrypted)} bytes")
    print(f"Decrypted preview: {decrypted[:100]}")
    
    if decrypted == plaintext:
        print("\n✓✓✓ ROUND-TRIP SUCCESS: decrypt(encrypt(plaintext)) == plaintext ✓✓✓")
    else:
        print("\nFAIL: decrypted != plaintext!")
        # Find first difference
        for i, (a, b) in enumerate(zip(decrypted, plaintext)):
            if a != b:
                print(f"  First diff at byte {i}: '{a}' vs '{b}' (hex: {ord(a):02x} vs {ord(b):02x})")
                print(f"  Context dec: {decrypted[max(0,i-20):i+20]}")
                print(f"  Context pt:  {plaintext[max(0,i-20):i+20]}")
                break
        sys.exit(1)
except Exception as e:
    print(f"FAIL: decrypt raised exception: {e}")
    sys.exit(1)

# ── Step 5: Verify PWD_WA blob structure ──
print("\n=== Step 5: Verify PWD_WA blob ===")
import base64
blob_b64 = pwd_hash.split(":")[-1]  # Extract after last ":"
blob = base64.urlsafe_b64decode(blob_b64 + "===")  # Add padding for decode
print(f"PWD_WA blob: {len(blob)} bytes (expect 338)")
print(f"  version={blob[0]}, key_id={blob[1]}, iv=12B, enc_key_len=2B, enc_key=256B, tag=16B, ctxt=50B")

if len(blob) != 338:
    print("FAIL: PWD_WA blob size wrong!")
    sys.exit(1)

print("\n✓ ALL TESTS PASSED ✓")
