"""
KAT verification against whatsapp-rust test vectors.
Validates HKDF → AES-CM KDF → IV → AES-CTR → WARP MI.
"""
import hashlib
import hmac
import struct
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# ═══ KAT inputs ═══
CALL_KEY = bytes.fromhex("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f")
PEER_LID = "222222222222222:0@lid"
SELF_LID = "111111111111111:0@lid"
SSRC = 0x12345678
SEQ = 7
ROC = 0
PAYLOAD = bytes.fromhex("102132435465768798a9bacb")

# ═══ KAT expected ═══
EXP_WAHKDF_OKM46 = "3f5423fb6f67e4c588bf5741a3a4e92c749ee99101a47c82bb5dacec40cfc7b95d387fe9ff466f78db6cc4fdaa30"
EXP_MASTER_KEY = "3f5423fb6f67e4c588bf5741a3a4e92c"
EXP_MASTER_SALT = "749ee99101a47c82bb5dacec40cf"
EXP_PEER_CIPHER = "747055a9d18be0fcdc0e29d871309081"
EXP_PEER_SALT = "10fb8133eff7639cc0d06788f49c"
EXP_PEER_AUTH = "8eff4bb04971d92512b034ce0ebc466059bfc6ea"
EXP_RTP_IV = "10fb8133fdc335e4c0d06788f49b0000"
EXP_CIPHER_OUT = "17b30591a2650ed7bbae9c5a"
EXP_WARP_MI4 = "53fada83"
EXP_SAMPLE_PACKET = bytes.fromhex("90780007000003c012345678deadbeef")
EXP_SAMPLE_ROC = 0

SRTP_LABEL_ENC = 0x00
SRTP_LABEL_AUTH = 0x01
SRTP_LABEL_SALT = 0x02

def hkdf_sha256(salt, ikm, info, length):
    if len(salt) == 0:
        salt = b'\x00' * 32
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    result, t, i = b"", b"", 1
    while len(result) < length:
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        result += t; i += 1
    return result[:length]

def aes_ctr(key, iv, data):
    c = Cipher(algorithms.AES(key), modes.CTR(iv))
    return c.encryptor().update(data) + c.encryptor().finalize()

def aes_cm_kdf(mk, ms, label, length):
    iv = bytearray(16)
    iv[:14] = ms[:14]
    iv[7] ^= label
    return aes_ctr(mk, bytes(iv), b'\x00' * length)

def build_e2e_iv(salt, ssrc, roc, seq):
    iv = bytearray(16)
    n = min(len(salt), 14)
    off = 14 - n
    iv[off:off+n] = salt[:n]
    iv[4] ^= (ssrc >> 24) & 0xFF
    iv[5] ^= (ssrc >> 16) & 0xFF
    iv[6] ^= (ssrc >> 8) & 0xFF
    iv[7] ^= ssrc & 0xFF
    pkt = ((roc & 0xFFFFFFFF) << 16) | (seq & 0xFFFF)
    hi16 = (pkt >> 32) & 0xFFFF
    lo32 = pkt & 0xFFFFFFFF
    iv[8] ^= (hi16 >> 8) & 0xFF
    iv[9] ^= hi16 & 0xFF
    iv[10] ^= (lo32 >> 24) & 0xFF
    iv[11] ^= (lo32 >> 16) & 0xFF
    iv[12] ^= (lo32 >> 8) & 0xFF
    iv[13] ^= lo32 & 0xFF
    return bytes(iv)

passed = 0
failed = 0

def check(name, got, expected_hex):
    global passed, failed
    exp = bytes.fromhex(expected_hex) if isinstance(expected_hex, str) else expected_hex
    if got == exp:
        print(f"  PASS: {name}")
        passed += 1
    else:
        print(f"  FAIL: {name}")
        print(f"    got:      {got.hex() if isinstance(got, bytes) else got}")
        print(f"    expected: {exp.hex() if isinstance(exp, bytes) else exp}")
        failed += 1

print("=== STEP 1: HKDF-SHA256 (WAHKDF) ===")
okm = hkdf_sha256(b'\x00'*32, CALL_KEY, PEER_LID.encode(), 46)
check("HKDF OKM46", okm, EXP_WAHKDF_OKM46)
check("master key (0:16)", okm[:16], EXP_MASTER_KEY)
check("master salt (16:30)", okm[16:30], EXP_MASTER_SALT)

mk = okm[:16]
ms = okm[16:30]

print("\n=== STEP 2: AES-CM KDF (session keys) ===")
sk = aes_cm_kdf(mk, ms, SRTP_LABEL_ENC, 16)
ss = aes_cm_kdf(mk, ms, SRTP_LABEL_SALT, 14)
ak = aes_cm_kdf(mk, ms, SRTP_LABEL_AUTH, 20)
check("cipher_key", sk, EXP_PEER_CIPHER)
check("salt", ss, EXP_PEER_SALT)
check("auth_key", ak, EXP_PEER_AUTH)

print("\n=== STEP 3: RTP IV ===")
iv = build_e2e_iv(ss, SSRC, ROC, SEQ)
check("RTP IV", iv, EXP_RTP_IV)

print("\n=== STEP 4: AES-CTR encrypt ===")
ct = aes_ctr(sk, iv, PAYLOAD)
check("cipher_out", ct, EXP_CIPHER_OUT)
# Round-trip
pt = aes_ctr(sk, iv, ct)
check("round-trip", pt, PAYLOAD.hex())

print("\n=== STEP 5: WARP MI tag ===")
mac = hmac.new(ak, digestmod=hashlib.sha1)
mac.update(EXP_SAMPLE_PACKET)
mac.update(struct.pack("!I", EXP_SAMPLE_ROC))
mi = mac.digest()[:4]
check("warp_mi_tag4", mi, EXP_WARP_MI4)

print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL KAT VECTORS MATCH — our implementation is correct!")
