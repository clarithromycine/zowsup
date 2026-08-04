"""
End-to-end decryption verification using Rust whatsapp-rust algorithms.
Tests: HBH → E2E → SFrame on captured WARP frames.
"""
import hashlib
import hmac
import struct
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ── From log: call 00FC78F722D46E5E066199831CB869B3 ──
CALL_KEY = bytes.fromhex("95a67af8a9218e61a32461783e665350a458dec2897431bd26510c3442d08369")
OUR_JID = "34197200736283:0@lid"
PEER_JID = "248846345101511:0@lid"
HBH_KEY = bytes.fromhex("93343fed7180f58d3834d7ccad4943404768fa6462caf548c5eb2c4b7877")
RECV_MASTER_KEY = bytes.fromhex("a0dd6ac38f9ccf332f1a6d7fdd60daca")
RECV_MASTER_SALT = bytes.fromhex("3735781f2bc002f6aad2893695d3")

# Frame #2: seq=1 ssrc=0xa50d9871
FRAME_HEX = "9078000100015cc0a50d9871debe0002d3000043800000009702e18ed2caf4e81a5f53e5c86fe9bbcb779f46a85511f2"
FRAME = bytes.fromhex(FRAME_HEX)
FRAME_SSRC = 0xa50d9871
FRAME_SEQ = 0x0001

# Parse WARP frame
FLAGS = (FRAME[14] << 8) | FRAME[15]
HDR_SIZE = 20 if (FLAGS & 1) else 16  # 16 for speech (X=0)
WARP_HDR = FRAME[:HDR_SIZE]
ENCRYPTED = FRAME[HDR_SIZE:-4]  # 28 bytes
MI_TAG = FRAME[-4:]

print(f"Frame: seq={FRAME_SEQ} ssrc=0x{FRAME_SSRC:08x} hdr={HDR_SIZE}B enc={len(ENCRYPTED)}B mi={MI_TAG.hex()}")
print(f"WARP header: {WARP_HDR.hex()}")

# ═══════════════════════════════════════════════════════════════
# HKDF-SHA256 helper
# ═══════════════════════════════════════════════════════════════
def hkdf_sha256(salt, ikm, info, length):
    if len(salt) == 0:
        salt = b'\x00' * 32
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    result, t, i = b"", b"", 1
    while len(result) < length:
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        result += t; i += 1
    return result[:length]

# ═══════════════════════════════════════════════════════════════
# STEP 1: HBH key derivation (Rust hbh_srtp.rs)
# ═══════════════════════════════════════════════════════════════
print("\n=== STEP 1: HBH key derivation (two-stage HKDF) ===")

# master_key = hbh_key[0:16], master_salt = hbh_key[16:30]
hbh_mk = HBH_KEY[:16]
hbh_ms = HBH_KEY[16:30]

# Stage 1: srtcp_salt = HKDF(salt=zeros32, ikm=master_salt, info="uplink hbh srtcp salt", L=32)
srtcp_salt = hkdf_sha256(b'\x00'*32, hbh_ms, b"uplink hbh srtcp salt", 32)
print(f"srtcp_salt: {srtcp_salt.hex()}")

# Stage 2: result = HKDF(salt=srtcp_salt, ikm=master_key, info="uplink hbh srtcp key", L=30)
hbh_derived_30 = hkdf_sha256(srtcp_salt, hbh_mk, b"uplink hbh srtcp key", 30)
print(f"hbh_derived_30: {hbh_derived_30.hex()}")

# Derived key = 30B: [0:16] = AES key, [16:30] = salt
hbh_aes_key = hbh_derived_30[:16]
hbh_salt = hbh_derived_30[16:30]
print(f"hbh_aes_key: {hbh_aes_key.hex()}")
print(f"hbh_salt: {hbh_salt.hex()}")

# ═══════════════════════════════════════════════════════════════
# STEP 2: HBH session key expansion (libsrtp AES-ICM KDF)
# ═══════════════════════════════════════════════════════════════
print("\n=== STEP 2: HBH session key expansion ===")

def aes_icm_crypt(key30, iv16, data):
    """libsrtp AES-ICM: 2-byte carry counter (bytes 15 then 14)."""
    aes_key = key30[:16]
    salt = key30[16:30]
    # counter = salt XOR iv (salt zero-padded to 16)
    counter = bytearray(16)
    counter[:14] = salt
    for i in range(16):
        counter[i] ^= iv16[i]
    
    cipher = Cipher(algorithms.AES(bytes(aes_key)), modes.ECB())
    encryptor = cipher.encryptor()
    
    out = bytearray(data)
    pos = 0
    while pos < len(out):
        ks = encryptor.update(bytes(counter))
        n = min(16, len(out) - pos)
        for j in range(n):
            out[pos + j] ^= ks[j]
        pos += n
        # 2-byte carry: increment byte 15, carry to byte 14
        counter[15] = (counter[15] + 1) & 0xFF
        if counter[15] == 0:
            counter[14] = (counter[14] + 1) & 0xFF
    return bytes(out)

def hbh_derive_session_bytes(master_key, master_salt, label, length):
    """libsrtp KDF: IV is all-zero except byte 7 = label."""
    kdf_key = master_key + master_salt  # 30 bytes
    iv = bytearray(16)
    iv[7] = label
    return aes_icm_crypt(kdf_key, bytes(iv), b'\x00' * length)

# Expand session keys
hbh_session_key = hbh_derive_session_bytes(hbh_aes_key, hbh_salt, 0x00, 16)
hbh_session_salt = hbh_derive_session_bytes(hbh_aes_key, hbh_salt, 0x02, 14)
hbh_auth_key = hbh_derive_session_bytes(hbh_aes_key, hbh_salt, 0x01, 20)
print(f"session_key:  {hbh_session_key.hex()}")
print(f"session_salt: {hbh_session_salt.hex()}")
print(f"auth_key:     {hbh_auth_key.hex()}")

# ═══════════════════════════════════════════════════════════════
# STEP 3: HBH decrypt (Rust build_rtp_icm_nonce)
# ═══════════════════════════════════════════════════════════════
print("\n=== STEP 3: HBH decrypt ===")

def build_hbh_nonce(ssrc, packet_index):
    """HBH RTP ICM nonce: ALL ZERO, SSRC at 4-7, pkt<<16 at 8-15."""
    iv = bytearray(16)  # all zero
    iv[4:8] = struct.pack("!I", ssrc)
    iv[8:16] = struct.pack("!Q", (packet_index & 0xFFFFFFFFFFFF) << 16)
    return bytes(iv)

pkt_idx = FRAME_SEQ  # ROC=0 for now
hbh_nonce = build_hbh_nonce(FRAME_SSRC, pkt_idx)
print(f"HBH nonce: {hbh_nonce.hex()}")

# HBH decrypt the encrypted payload
hbh_key30 = hbh_session_key + hbh_session_salt  # 30 bytes
hbh_decrypted = aes_icm_crypt(hbh_key30, hbh_nonce, ENCRYPTED)
print(f"HBH decrypted ({len(hbh_decrypted)}B): {hbh_decrypted.hex()}")

# Check if it looks like RTP
if len(hbh_decrypted) >= 12:
    v = (hbh_decrypted[0] >> 6) & 3
    pt = hbh_decrypted[1] & 0x7F
    rtp_ssrc = struct.unpack("!I", hbh_decrypted[8:12])[0]
    rtp_seq = struct.unpack("!H", hbh_decrypted[2:4])[0]
    print(f"  As RTP: V={v} PT={pt} SSRC=0x{rtp_ssrc:08x} seq={rtp_seq}")

# ═══════════════════════════════════════════════════════════════
# STEP 4: E2E SRTP decrypt (standard, same as before but verify)
# ═══════════════════════════════════════════════════════════════
print("\n=== STEP 4: E2E decrypt ===")

def aes_ctr(key, iv, data):
    c = Cipher(algorithms.AES(key), modes.CTR(iv))
    return c.encryptor().update(data)

def derive_srtp_key(mk, ms, label, length):
    iv = bytearray(16)
    iv[:14] = ms[:14]
    iv[7] ^= label
    return aes_ctr(mk, bytes(iv), b'\x00' * length)

def build_e2e_iv(salt, ssrc, seq, roc=0):
    """Rust build_e2e_rtp_iv: salt RIGHT-aligned, SSRC@4-7, pkt_idx[2:8]@8-13."""
    iv = bytearray(16)
    n = min(len(salt), 14)
    off = 14 - n
    iv[off:off+n] = salt[:n]
    iv[4] ^= (ssrc >> 24) & 0xFF
    iv[5] ^= (ssrc >> 16) & 0xFF
    iv[6] ^= (ssrc >> 8) & 0xFF
    iv[7] ^= ssrc & 0xFF
    pkt_idx = (roc << 16) | seq
    hi16 = ((pkt_idx >> 32) & 0xFFFF)
    lo32 = pkt_idx & 0xFFFFFFFF
    iv[8] ^= (hi16 >> 8) & 0xFF
    iv[9] ^= hi16 & 0xFF
    iv[10] ^= (lo32 >> 24) & 0xFF
    iv[11] ^= (lo32 >> 16) & 0xFF
    iv[12] ^= (lo32 >> 8) & 0xFF
    iv[13] ^= lo32 & 0xFF
    return bytes(iv)

e2e_sk = derive_srtp_key(RECV_MASTER_KEY, RECV_MASTER_SALT, 0x00, 16)
e2e_ss = derive_srtp_key(RECV_MASTER_KEY, RECV_MASTER_SALT, 0x02, 14)
e2e_ak = derive_srtp_key(RECV_MASTER_KEY, RECV_MASTER_SALT, 0x01, 20)
print(f"E2E session_key:  {e2e_sk.hex()}")
print(f"E2E session_salt: {e2e_ss.hex()}")
print(f"E2E auth_key:     {e2e_ak.hex()}")

# If HBH produced an RTP-like output, extract E2E payload
# Otherwise try E2E on the raw encrypted data (no HBH)
e2e_input = hbh_decrypted  # try HBH output first

# If HBH output looks like RTP, extract payload
if len(e2e_input) >= 12:
    v_check = (e2e_input[0] >> 6) & 3
    if v_check == 2:
        # Standard RTP: skip header, strip auth tag
        rtp_hdr_sz = 12
        e2e_payload = e2e_input[rtp_hdr_sz:-4]  # -4 for SRTP auth
        e2e_rtp_ssrc = struct.unpack("!I", e2e_input[8:12])[0]
        e2e_rtp_seq = struct.unpack("!H", e2e_input[2:4])[0]
        print(f"\nHBH output is valid RTP (V=2)! Extracting E2E payload.")
        print(f"  RTP SSRC: 0x{e2e_rtp_ssrc:08x} RTP seq: {e2e_rtp_seq}")
    else:
        # Not valid RTP - try the whole HBH output as E2E encrypted blob
        # Strip 4-byte auth tag (SRTP convention)
        e2e_payload = e2e_input[:-4] if len(e2e_input) > 4 else e2e_input
        e2e_rtp_ssrc = FRAME_SSRC
        e2e_rtp_seq = FRAME_SEQ
        print(f"\nHBH output NOT valid RTP (V={v_check}). Trying whole as E2E blob.")
else:
    e2e_payload = e2e_input
    e2e_rtp_ssrc = FRAME_SSRC
    e2e_rtp_seq = FRAME_SEQ

print(f"E2E input ({len(e2e_payload)}B): {e2e_payload.hex()}")

# E2E decrypt
e2e_iv = build_e2e_iv(e2e_ss, e2e_rtp_ssrc, e2e_rtp_seq)
e2e_decrypted = aes_ctr(e2e_sk, e2e_iv, e2e_payload)
print(f"E2E decrypted ({len(e2e_decrypted)}B): {e2e_decrypted[:64].hex()}")

# ═══════════════════════════════════════════════════════════════
# STEP 5: SFrame decrypt (Rust sframe.rs)
# ═══════════════════════════════════════════════════════════════
print("\n=== STEP 5: SFrame decrypt ===")

def derive_sframe_key(call_key, participant_id):
    """Rust: HKDF(salt=callKey[0:16], ikm=callKey[16:32], info="e2e sframe key"+id, L=32)"""
    info = b"e2e sframe key" + participant_id.encode()
    return hkdf_sha256(call_key[:16], call_key[16:32], info, 32)

# SFrame direction: recv_key = derive(callKey, SELF_JID) ← phone encrypts with OUR key!
sf_recv_key = derive_sframe_key(CALL_KEY, OUR_JID)
print(f"SFrame recv key (our JID): {sf_recv_key[:16].hex()}")

def decode_varint(data, offset):
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

def sframe_decrypt(recv_key_bytes, frame):
    """Rust SframeSession::decrypt: trailing-header layout."""
    if len(frame) < 16 + 3:  # at least tag(16) + min header(3)
        return "TOO_SHORT", frame
    
    header_len = frame[-1]  # last byte = total header length
    if header_len < 3 or header_len > len(frame):
        return "BAD_HEADER_LEN", frame
    
    header_start = len(frame) - header_len
    header = frame[header_start:]
    ciphertext_with_tag = frame[:header_start]
    
    if len(ciphertext_with_tag) < 16 + 1:
        return "NO_CIPHERTEXT", frame
    
    # Parse header: counter(varint) + key_id(varint) + total_len(1B, already read)
    counter, next_off = decode_varint(header, 0)
    if counter is None:
        return "BAD_COUNTER", frame
    key_id, _ = decode_varint(header, next_off)
    if key_id is None:
        return "BAD_KEY_ID", frame
    
    # GCM nonce: 8 zero bytes + counter as LE u64
    nonce = b'\x00' * 8 + struct.pack("<Q", counter)
    
    try:
        aesgcm = AESGCM(recv_key_bytes[:16])
        plain = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
        return "DECRYPTED", plain
    except Exception as e:
        return f"GCM_FAIL:{e}", frame

# Try SFrame on E2E output
result, data = sframe_decrypt(sf_recv_key, e2e_decrypted)
print(f"SFrame result: {result}")
if result == "DECRYPTED":
    print(f"  Plaintext ({len(data)}B): {data.hex()}")
    if data:
        b0 = data[0]
        print(f"  First byte: 0x{b0:02x} ({b0:08b})")
        if (b0 & 0x80) == 0x80:
            print("  → MLow CELT mode!")
        if b0 in (0xFC, 0xF8, 0xF0, 0xE0):
            print("  → Opus TOC!")

# ═══════════════════════════════════════════════════════════════
# STEP 6: Verify WARP MI with SRTP auth_key (not warp_auth_key)
# ═══════════════════════════════════════════════════════════════
print("\n=== STEP 6: WARP MI with E2E auth_key ===")
mac = hmac.new(e2e_ak, digestmod=hashlib.sha1)
mac.update(FRAME[:-4])  # everything except MI tag
mac.update(struct.pack("!I", 0))  # ROC=0
computed_mi = mac.digest()[:4]
print(f"Computed MI (E2E auth_key): {computed_mi.hex()}")
print(f"Frame MI tag:               {MI_TAG.hex()}")
print(f"Match: {computed_mi == MI_TAG}")

# ═══════════════════════════════════════════════════════════════
# STEP 7: Try downlink HBH (receive direction)
# ═══════════════════════════════════════════════════════════════
print("\n=== STEP 7: HBH with DOWNLINK labels ===")
srtcp_salt_dl = hkdf_sha256(b'\x00'*32, hbh_ms, b"downlink hbh srtcp salt", 32)
hbh_dl_30 = hkdf_sha256(srtcp_salt_dl, hbh_mk, b"downlink hbh srtcp key", 30)
hbh_dl_key = hbh_dl_30[:16]
hbh_dl_salt = hbh_dl_30[16:30]
hbh_dl_sk = hbh_derive_session_bytes(hbh_dl_key, hbh_dl_salt, 0x00, 16)
hbh_dl_ss = hbh_derive_session_bytes(hbh_dl_key, hbh_dl_salt, 0x02, 14)
hbh_dl_key30 = hbh_dl_sk + hbh_dl_ss
hbh_dl_dec = aes_icm_crypt(hbh_dl_key30, build_hbh_nonce(FRAME_SSRC, FRAME_SEQ), ENCRYPTED)
print(f"HBH downlink decrypt: {hbh_dl_dec[:32].hex()}")
v_dl = (hbh_dl_dec[0] >> 6) & 3 if len(hbh_dl_dec) > 0 else -1
print(f"  V={v_dl}")

# ═══════════════════════════════════════════════════════════════
# STEP 8: Skip HBH — E2E directly on raw encrypted data, then SFrame
# ═══════════════════════════════════════════════════════════════
print("\n=== STEP 8: E2E direct → SFrame (no HBH) ===")
e2e_direct_iv = build_e2e_iv(e2e_ss, FRAME_SSRC, FRAME_SEQ)
e2e_direct = aes_ctr(e2e_sk, e2e_direct_iv, ENCRYPTED[:-4])  # -4 for MI? No, ENCRYPTED is already without MI
# Actually, ENCRYPTED = FRAME[HDR_SIZE:-4] which excludes MI tag
e2e_direct_full = aes_ctr(e2e_sk, e2e_direct_iv, ENCRYPTED)
print(f"E2E direct ({len(e2e_direct_full)}B): {e2e_direct_full.hex()}")

# Try SFrame on E2E output
print(f"\nSFrame on E2E output:")
sf_result, sf_data = sframe_decrypt(sf_recv_key, e2e_direct_full)
print(f"  Result: {sf_result}")
if sf_result == "DECRYPTED":
    print(f"  Plaintext: {sf_data.hex()}")

# Also try SFrame with PEER key (opposite direction)
sf_peer_key = derive_sframe_key(CALL_KEY, PEER_JID)
sf_result2, sf_data2 = sframe_decrypt(sf_peer_key, e2e_direct_full)
print(f"  With peer key: {sf_result2}")

# ═══════════════════════════════════════════════════════════════
# STEP 9: Try E2E on full raw data including MI tag
# ═══════════════════════════════════════════════════════════════
print("\n=== STEP 9: E2E on payload INCLUDING MI tag ===")
full_payload = FRAME[HDR_SIZE:]  # including MI
e2e_full_iv = build_e2e_iv(e2e_ss, FRAME_SSRC, FRAME_SEQ)
e2e_full_dec = aes_ctr(e2e_sk, e2e_full_iv, full_payload)
print(f"E2E on full payload ({len(full_payload)}B): {e2e_full_dec[:48].hex()}")
sf_result3, sf_data3 = sframe_decrypt(sf_recv_key, e2e_full_dec)
print(f"  SFrame: {sf_result3}")

# ═══════════════════════════════════════════════════════════════
# STEP 10: Try different SFrame key derivation (maybe participant ID format differs)
# ═══════════════════════════════════════════════════════════════
print("\n=== STEP 10: SFrame with different participant ID formats ===")
for pid in [OUR_JID, PEER_JID, "34197200736283@lid", "248846345101511@lid",
            "34197200736283:0@lid", "248846345101511:0@lid"]:
    sk = derive_sframe_key(CALL_KEY, pid)
    r, d = sframe_decrypt(sk, e2e_direct_full)
    if r == "DECRYPTED":
        print(f"  MATCH with {pid}: {d[:16].hex()}")
    else:
        print(f"  {pid}: {r}")
