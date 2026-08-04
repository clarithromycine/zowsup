"""
Runtime verification: use ACTUAL log values to verify E2E decryption.
Takes the latest call's callKey, peerLID, and first RX frame, and verifies
key derivation + decryption step by step.
"""
import hashlib, hmac, struct
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# ═══ From latest log (call 00843381603A1B0253B2EBCD6F9B5FFF) ═══
CALL_KEY = bytes.fromhex("26bd4acbc9c0ad9a17664a82a922b0f61e8c152134a249752515b3c2cf62c0b0")
# Wait - this call_key is from an earlier call. Let me use the latest one.
# Actually, the log shows: call_key=26bd4acbc9c0ad9a17664a82a922b0f61e8c152134a249752515b3c2cf62c0b0
# Let me use the frame data from the same call.
# Frame #2: 9078000100034080436d7592debe0002d300004380000000c4305c6c43c2d68bf83fc2d2a095ab92188a01aafd5d157a
# Actually that's from an earlier call too.

# Let me use the most recent log values:
# From the log: call_key=b4c88c5ebc20b26c747bbb687019df52eaa6c747d8808e863aecf4f5a3ff3c54
# recv_master=48196fc409a22e5a42c44da24e21bd7c
# First RX frame: 81ca00075e3bc1c84740247f4d4b9ecfe054a5cfa42165f12fa8fb779f5b2fc18000000167a833c1761283bcd7f8
# Frame #2: 90780001000232805e3bc1c8debe0002d3000043800000001dae0b42e08a9f0e57eed69eca056e13361cc76a96486aa882aa9e

# Let me use the call that had the clearest data
CALL_KEY = bytes.fromhex("b4c88c5ebc20b26c747bbb687019df52eaa6c747d8808e863aecf4f5a3ff3c54")
PEER_LID = "248846345101511:0@lid"
RECV_MASTER_KEY = bytes.fromhex("48196fc409a22e5a42c44da24e21bd7c")
RECV_MASTER_SALT = bytes.fromhex("1ebf07f6eb70df8aff8ba0dbfae3")

# Frame #2 (9078, seq=1):
FRAME = bytes.fromhex("90780001000232805e3bc1c8debe0002d3000043800000001dae0b42e08a9f0e57eed69eca056e13361cc76a96486aa882aa9e")
HDR = 16  # flags=0002, X=0
ENC = FRAME[HDR:-4]  # strip hdr + MI
MI = FRAME[-4:]
FRAME_SSRC = 0x5e3bc1c8
FRAME_SEQ = 1

SRTP_LABEL_ENC = 0x00
SRTP_LABEL_SALT = 0x02
SRTP_LABEL_AUTH = 0x01

def hkdf_sha256(salt, ikm, info, length):
    if len(salt) == 0: salt = b'\x00' * 32
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    result, t, i = b"", b"", 1
    while len(result) < length:
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        result += t; i += 1
    return result[:length]

def aes_ctr(key, iv, data):
    c = Cipher(algorithms.AES(key), modes.CTR(iv))
    e = c.encryptor()
    return e.update(data) + e.finalize()

def aes_cm_kdf(mk, ms, label, length):
    iv = bytearray(16); iv[:14] = ms[:14]; iv[7] ^= label
    return aes_ctr(mk, bytes(iv), b'\x00' * length)

def build_e2e_iv(salt, ssrc, roc, seq):
    iv = bytearray(16)
    n = min(len(salt), 14); off = 14 - n
    iv[off:off+n] = salt[:n]
    iv[4] ^= (ssrc >> 24) & 0xFF; iv[5] ^= (ssrc >> 16) & 0xFF
    iv[6] ^= (ssrc >> 8) & 0xFF; iv[7] ^= ssrc & 0xFF
    pkt = ((roc & 0xFFFFFFFF) << 16) | (seq & 0xFFFF)
    iv[8] ^= ((pkt >> 40) & 0xFF); iv[9] ^= ((pkt >> 32) & 0xFF)
    iv[10] ^= ((pkt >> 24) & 0xFF); iv[11] ^= ((pkt >> 16) & 0xFF)
    iv[12] ^= ((pkt >> 8) & 0xFF); iv[13] ^= (pkt & 0xFF)
    return bytes(iv)

print("=== 1. HKDF verification ===")
okm = hkdf_sha256(b'\x00'*32, CALL_KEY, PEER_LID.encode(), 46)
mk = okm[:16]; ms = okm[16:30]
print(f"Derived master_key:  {mk.hex()}")
print(f"Log    master_key:  {RECV_MASTER_KEY.hex()}")
print(f"MATCH: {mk == RECV_MASTER_KEY}")
print(f"Derived master_salt: {ms.hex()}")
print(f"Log    master_salt: {RECV_MASTER_SALT.hex()}")
print(f"MATCH: {ms == RECV_MASTER_SALT}")

if mk != RECV_MASTER_KEY:
    print("\n*** MASTER KEY MISMATCH! Trying alternative LIDs:")
    for alt in ["248846345101511@lid", "248846345101511:9@lid", "248846345101511.1:0@lid"]:
        okm2 = hkdf_sha256(b'\x00'*32, CALL_KEY, alt.encode(), 46)
        if okm2[:16] == RECV_MASTER_KEY:
            print(f"  MATCH with LID: {alt}")
        else:
            print(f"  {alt}: mk={okm2[:4].hex()}..")

print("\n=== 2. Session key derivation ===")
sk = aes_cm_kdf(RECV_MASTER_KEY, RECV_MASTER_SALT, SRTP_LABEL_ENC, 16)
ss = aes_cm_kdf(RECV_MASTER_KEY, RECV_MASTER_SALT, SRTP_LABEL_SALT, 14)
ak = aes_cm_kdf(RECV_MASTER_KEY, RECV_MASTER_SALT, SRTP_LABEL_AUTH, 20)
print(f"session_key:  {sk.hex()}")
print(f"session_salt: {ss.hex()}")
print(f"auth_key:     {ak.hex()}")

print("\n=== 3. Frame parsing ===")
print(f"Frame: type=0x{(FRAME[0]<<8)|FRAME[1]:04x} seq={FRAME_SEQ} ssrc=0x{FRAME_SSRC:08x}")
print(f"Header: {FRAME[:HDR].hex()}")
print(f"Encrypted ({len(ENC)}B): {ENC.hex()}")
print(f"MI tag: {MI.hex()}")

print("\n=== 4. WARP MI verification ===")
mac = hmac.new(ak, digestmod=hashlib.sha1)
mac.update(FRAME[:-4])
mac.update(struct.pack("!I", 0))
mi_calc = mac.digest()[:4]
print(f"Computed MI: {mi_calc.hex()}")
print(f"Frame MI:    {MI.hex()}")
print(f"MATCH: {mi_calc == MI}")

print("\n=== 5. Decrypt ===")
iv = build_e2e_iv(ss, FRAME_SSRC, 0, FRAME_SEQ)
print(f"IV: {iv.hex()}")
dec = aes_ctr(sk, iv, ENC)
print(f"Decrypted ({len(dec)}B): {dec.hex()}")
print(f"First byte: 0x{dec[0]:02x}")
# Print full decrypted for inspection
print(f"Full decrypted: {dec[:48].hex()}")

print("\n=== 6. Try decoding ===")
from voip.media.codec import OpusCodec
c = OpusCodec()
# Pad to minimum opus frame size
test = dec + b'\x00' * max(0, 3 - len(dec))
result = c.decode(test)
print(f"Decode: {len(result)} samples, first5={result[:5]}")
c.close()
