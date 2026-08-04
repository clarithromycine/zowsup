"""Verify plaintext length calculation byte-by-byte."""
import base64, json
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.Random import get_random_bytes
from Crypto.Hash import SHA1

# Simulate our exact code path for a fixed scenario
PASSWORD_CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+{}"

def _b64_urlsafe_nopad(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def _jj5_a01(public_key):
    der = public_key.export_key(format="DER")
    b64 = base64.b64encode(der).decode()
    result = f"-----BEGIN PUBLIC KEY-----\n{b64}\n-----END PUBLIC KEY-----\n"
    return result

def build_pwd_wa_hash(password, key_id, pubkey_pem, timestamp):
    rsa_pub = RSA.import_key(pubkey_pem.strip().encode())
    aes_key = get_random_bytes(32)
    iv = get_random_bytes(12)
    cipher = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
    ctxt, tag = cipher.encrypt_and_digest(password.encode("utf-8"))
    enc_key = PKCS1_v1_5.new(rsa_pub).encrypt(aes_key)
    elen = len(enc_key)
    blob = bytearray()
    blob.append(1)
    blob.append(key_id & 0xFF)
    blob.extend(iv)
    blob.extend(elen.to_bytes(2, "little"))
    blob.extend(enc_key)
    blob.extend(tag)
    blob.extend(ctxt)
    return f"#PWD_WA:11:{timestamp}:{_b64_urlsafe_nopad(bytes(blob))}"

# Generate fixed params
import secrets
password = "".join(secrets.choice(PASSWORD_CHARSET) for _ in range(50))
ts = 1784171208
keypair = RSA.generate(2048)
pub_pem = _jj5_a01(keypair.publickey())

# Build PWD_WA blob first to check its size  
rsa_pub = RSA.import_key(pub_pem.strip().encode())
aes_key = get_random_bytes(32)
iv = get_random_bytes(12)
cipher = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
ctxt, tag = cipher.encrypt_and_digest(password.encode("utf-8"))
enc_key = PKCS1_v1_5.new(rsa_pub).encrypt(aes_key)
blob = bytearray()
blob.append(1)
blob.append(1)  # key_id
blob.extend(iv)
blob.extend(len(enc_key).to_bytes(2, "little"))
blob.extend(enc_key)
blob.extend(tag)
blob.extend(ctxt)
print(f"Blob size: {len(blob)} bytes (expected 338)")
print(f"  version=1, key_id=1, iv=12, enc_key_len=2, enc_key={len(enc_key)}, tag=16, ctxt={len(ctxt)}")
b64 = _b64_urlsafe_nopad(bytes(blob))
print(f"  urlsafe b64: {len(b64)} chars (expected 451)")

# Build the exact plaintext
client_pub = _jj5_a01(keypair.publickey())
pwd_hash = f"#PWD_WA:11:{ts}:{b64}"

plaintext = json.dumps({
    "version": 1,
    "timestamp": ts,
    "password": pwd_hash,
    "client_pub_key": client_pub,
    "client_pub_key_type": "RSA 2048",
}, separators=(",", ":"))

print(f"\nPlaintext length: {len(plaintext)} bytes")
print(f"Plaintext preview (first 200): {plaintext[:200]}")
print(f"Plaintext preview (last 200): {plaintext[-200:]}")

# Break down component sizes
d = json.loads(plaintext)  # re-parse to verify
# Manual breakdown
parts = plaintext.split('"client_pub_key":"')
before_pub = parts[0] + '"client_pub_key":"'
after_start = parts[1]
pub_b64_and_rest = after_start.split('-----END PUBLIC KEY-----\\n')
pub_b64_part = pub_b64_and_rest[0]
rest = '-----END PUBLIC KEY-----\\n' + pub_b64_and_rest[1]

print(f"\n--- Component breakdown ---")
print(f"Before client_pub_key value: {len(before_pub)} chars")
print(f"  (includes: {repr(before_pub[-50:])})")
print(f"Pubkey DER base64 body: {len(pub_b64_part)} chars")
print(f"  (should be 392 for DER=294)")
print(f"Rest after pubkey b64: {len(rest)} chars")
print(f"  (first 60: {repr(rest[:60])})")

print(f"\nTotal = {len(before_pub)} + {len(pub_b64_part)} + {len(rest)} = {len(before_pub) + len(pub_b64_part) + len(rest)}")

# Also check DER size
der = keypair.publickey().export_key(format="DER")
print(f"\nDER size: {len(der)} bytes")
print(f"DER base64: {len(base64.b64encode(der).decode())} chars")
