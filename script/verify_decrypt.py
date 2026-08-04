"""
Offline E2E SRTP decryption verification.
Uses exact values from the log to confirm key derivation and decryption.

Usage: python script/verify_decrypt.py
"""
import hashlib
import hmac
import struct
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# ── From log: "SRTP keys" line ──
CALL_KEY = bytes.fromhex("b619754787a5525e125b98e26fcba2b43c4b32b327e56cb89d003588bae064d8")
OUR_JID = "34197200736283:0@lid"
PEER_JID = "248846345101511:0@lid"

# ── From log: "SRTP recv" line ──
RECV_MASTER_KEY = bytes.fromhex("b57982994cf90438128c541c7af1009f")
RECV_MASTER_SALT = bytes.fromhex("d3e684a67edfe5b382944b0c7bda")

# ── From log: RELAY RAW #1 ──
FRAME_HEX = "90780033000387c030d2e6a3debe00023001d3000043800068e10d119ae4c52e26452b2ebaf7228d6a2e51a4ad810f805560adc4f3eeccba684236db6309"
FRAME_BYTES = bytes.fromhex(FRAME_HEX)
FRAME_SSRC = 0x30d2e6a3   # from WARP header bytes 8-11
FRAME_SEQ = 0x0033         # from WARP header bytes 2-3

# ── Also try: first TX frame to verify send direction keys ──
TX_CALL_KEY = bytes.fromhex("b619754787a5525e125b98e26fcba2b43c4b32b327e56cb89d003588bae064d8")
TX_FRAME_HEX = "9078000100000000a57279cbdebe00006aba2b322c1f21a5da019804aabc598b3b7307"
TX_FRAME_BYTES = bytes.fromhex(TX_FRAME_HEX)
TX_SSRC = 0xa57279cb
TX_SEQ = 0x0001

SRTP_LABEL_ENCRYPTION = 0x00
SRTP_LABEL_AUTH = 0x01
SRTP_LABEL_SALT = 0x02


def _aes_ctr(key, iv, data):
    c = Cipher(algorithms.AES(key), modes.CTR(iv))
    return c.encryptor().update(data)


def derive_srtp_key(master_key, master_salt, label, length):
    """RFC 3711 §4.3 — matches Go deriveSrtpKey()"""
    iv = bytearray(16)
    iv[:14] = master_salt[:14]
    iv[7] ^= (label & 0xFF)
    return _aes_ctr(master_key, bytes(iv), b'\x00' * length)


def generate_iv(session_salt, ssrc, index):
    """Matches Go generateIV()"""
    iv = bytearray(16)
    iv[:14] = session_salt[:14]
    ssrc_bytes = struct.pack("!I", ssrc)
    for i in range(4):
        iv[4 + i] ^= ssrc_bytes[i]
    idx_bytes = struct.pack("!Q", index & 0xFFFFFFFFFFFF)[2:8]
    for i in range(6):
        iv[8 + i] ^= idx_bytes[i]
    return bytes(iv)


def hkdf_sha256(ikm, salt, info, length):
    """HKDF-SHA256 — matches Go hkdf.Key()"""
    if salt == b"":
        salt = b'\x00' * 32
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    result = b""
    t = b""
    i = 1
    while len(result) < length:
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        result += t
        i += 1
    return result[:length]


def derive_per_jid_srtp_key(call_key, device_jid):
    derived = hkdf_sha256(call_key, b"", device_jid.encode(), 46)
    return derived[0:16], derived[16:30]


print("=" * 70)
print("STEP 1: Verify HKDF derivation matches log")
print("=" * 70)

# Our derivation
mk, ms = derive_per_jid_srtp_key(CALL_KEY, PEER_JID)
print(f"Derived recv master_key:  {mk.hex()}")
print(f"Log    recv master_key:  {RECV_MASTER_KEY.hex()}")
print(f"Match: {mk == RECV_MASTER_KEY}")

print(f"Derived recv master_salt: {ms.hex()}")
print(f"Log    recv master_salt: {RECV_MASTER_SALT.hex()}")
print(f"Match: {ms == RECV_MASTER_SALT}")

print()
print("=" * 70)
print("STEP 2: Derive SRTP session keys")
print("=" * 70)

session_key = derive_srtp_key(RECV_MASTER_KEY, RECV_MASTER_SALT, SRTP_LABEL_ENCRYPTION, 16)
session_salt = derive_srtp_key(RECV_MASTER_KEY, RECV_MASTER_SALT, SRTP_LABEL_SALT, 14)
auth_key = derive_srtp_key(RECV_MASTER_KEY, RECV_MASTER_SALT, SRTP_LABEL_AUTH, 20)

print(f"Session key:  {session_key.hex()}")
print(f"Session salt: {session_salt.hex()}")
print(f"Auth key:     {auth_key.hex()}")

print()
print("=" * 70)
print("STEP 3: Decrypt frame #1 (RX)")
print("=" * 70)

# Parse WARP frame
frame_type = (FRAME_BYTES[0] << 8) | FRAME_BYTES[1]
flags = (FRAME_BYTES[14] << 8) | FRAME_BYTES[15]
hdr_size = 20 if (flags & 1) else 16

print(f"Frame type: 0x{frame_type:04x}")
print(f"Flags: 0x{flags:04x} X={'DTX' if (flags & 1) else 'SPEECH'}")
print(f"Header size: {hdr_size}")
print(f"SSRC: 0x{FRAME_SSRC:08x}  Seq: {FRAME_SEQ}")
print(f"Total len: {len(FRAME_BYTES)}")

encrypted = FRAME_BYTES[hdr_size:-4]  # strip header and MI tag
mi_tag = FRAME_BYTES[-4:]
print(f"Encrypted payload ({len(encrypted)}B): {encrypted.hex()}")
print(f"MI tag: {mi_tag.hex()}")

# Generate IV
packet_index = FRAME_SEQ  # ROC=0 for first frame
iv = generate_iv(session_salt, FRAME_SSRC, packet_index)
print(f"IV: {iv.hex()}")

# Decrypt
decrypted = _aes_ctr(session_key, iv, encrypted)
print(f"Decrypted ({len(decrypted)}B): {decrypted.hex()}")
print(f"Decrypted as string: {decrypted[:32]}")

# Check if it looks like valid Opus/MLow
if decrypted:
    b0 = decrypted[0]
    print(f"First byte: 0x{b0:02x} ({b0:08b})")
    if (b0 & 0x80) == 0:
        print("  → MLow (bit7=0, no CELT) — could be comfort noise or SILK")
    else:
        print("  → CELT mode")

print()
print("=" * 70)
print("STEP 4.5: Compute warp_auth_key and verify MI")
print("=" * 70)
warp_key = hkdf_sha256(CALL_KEY, b"", b"warp auth key", 32)
log_warp_key = bytes.fromhex("53184104941c11857b0ef126ab7004b2476223ca9005edac754ab3f8899e2778")
print(f"Computed warp_auth_key:  {warp_key.hex()}")
print(f"Log     warp_auth_key:  {log_warp_key.hex()}")
print(f"Match: {warp_key == log_warp_key}")

# MI = HMAC-SHA1(warp_auth_key, hdr||encrypted||ROC_BE32)[:4]
mi_data = FRAME_BYTES[:hdr_size] + encrypted
for wk, label in [(warp_key, "computed"), (log_warp_key, "log")]:
    mac = hmac.new(wk, digestmod=hashlib.sha1)
    mac.update(mi_data)
    mac.update(struct.pack("!I", 0))
    print(f"  MI with {label} warp_auth_key: {mac.digest()[:4].hex()}")
print(f"  Frame MI tag:                     {mi_tag.hex()}")

# Also try: compute MI WITHOUT ROC
mac2 = hmac.new(warp_key, digestmod=hashlib.sha1)
mac2.update(mi_data)
print(f"  MI WITHOUT ROC:                    {mac2.digest()[:4].hex()}")

# Try: MI over FULL frame including header
mac3 = hmac.new(warp_key, digestmod=hashlib.sha1)
mac3.update(FRAME_BYTES[:-4])
mac3.update(struct.pack("!I", 0))
print(f"  MI over full_frame[:-4]+roc:       {mac3.digest()[:4].hex()}")

print()
print("=" * 70)
print("STEP 4: Verify WARP MI tag")
print("=" * 70)
# MI = HMAC-SHA1(warp_auth_key, hdr || ext || encrypted || ROC_BE)[:4]
warp_auth_key = bytes.fromhex("53184104941c11857b0ef126ab7004b2476223ca9005edac754ab3f8899e2778")
mi_data = FRAME_BYTES[:hdr_size] + encrypted
mac = hmac.new(warp_auth_key, digestmod=hashlib.sha1)
mac.update(mi_data)
mac.update(struct.pack("!I", 0))  # ROC=0
expected_mi = mac.digest()[:4]
print(f"Computed MI: {expected_mi.hex()}")
print(f"Frame   MI: {mi_tag.hex()}")
print(f"Match: {expected_mi == mi_tag}")

print()
print("=" * 70)
print("STEP 5: Try with different peer LIDs")
print("=" * 70)

alt_lids = [
    "248846345101511@lid",
    "248846345101511:0@lid",
    "248846345101511.1:0@lid",
    "248846345101511:9@lid",
]
for lid in alt_lids:
    mk2, ms2 = derive_per_jid_srtp_key(CALL_KEY, lid)
    if mk2 == RECV_MASTER_KEY:
        print(f"  ★ MATCH: {lid} → same master_key as recv")
    sk2 = derive_srtp_key(mk2, ms2, SRTP_LABEL_ENCRYPTION, 16)
    ss2 = derive_srtp_key(mk2, ms2, SRTP_LABEL_SALT, 14)
    iv2 = generate_iv(ss2, FRAME_SSRC, FRAME_SEQ)
    dec2 = _aes_ctr(sk2, iv2, encrypted)
    # Check for Opus TOC byte (0xFC for 20ms mono)
    looks_opus = (len(dec2) > 0 and (dec2[0] & 0xFC) in (0xF8, 0xF0, 0xE0, 0xC0, 0x80, 0x00))
    looks_mlow_silk = (len(dec2) > 0 and (dec2[0] & 0x80) == 0x00 and len(dec2) <= 6)
    print(f"  {lid}: dec[0]=0x{dec2[0]:02x} opus_like={looks_opus} mlow_silk={looks_mlow_silk} "
          f"dec={dec2[:16].hex()}")

print()
print("=" * 70)
print("STEP 6: Derive from raw peer_jid in log (without ensureDeviceJid)")
print("=" * 70)
raw_peer = "248846345101511@lid"  # as seen in the log
for suffix in ["", ":0", ":9", ".1:0"]:
    test_jid = raw_peer.replace("@lid", f"{suffix}@lid") if suffix else raw_peer
    mk3, ms3 = derive_per_jid_srtp_key(CALL_KEY, test_jid)
    sk3 = derive_srtp_key(mk3, ms3, SRTP_LABEL_ENCRYPTION, 16)
    ss3 = derive_srtp_key(mk3, ms3, SRTP_LABEL_SALT, 14)
    iv3 = generate_iv(ss3, FRAME_SSRC, FRAME_SEQ)
    dec3 = _aes_ctr(sk3, iv3, encrypted)
    print(f"  {test_jid}: mk={mk3[:4].hex()}.. dec={dec3[:16].hex()}")

print()
print("=" * 70)
print("STEP 7: Try decrypt with OUR send key (what if phone encrypts with our JID?)")
print("=" * 70)
send_mk, send_ms = derive_per_jid_srtp_key(CALL_KEY, OUR_JID)
print(f"Our send master_key:  {send_mk.hex()}")
sk_send = derive_srtp_key(send_mk, send_ms, SRTP_LABEL_ENCRYPTION, 16)
ss_send = derive_srtp_key(send_mk, send_ms, SRTP_LABEL_SALT, 14)
iv_send = generate_iv(ss_send, FRAME_SSRC, FRAME_SEQ)
dec_send = _aes_ctr(sk_send, iv_send, encrypted)
print(f"Decrypt with OUR send key: {dec_send[:32].hex()}")
print(f"  Looks valid? first_byte=0x{dec_send[0]:02x}")

print()
print("=" * 70)
print("STEP 8: What if the payload is actually PLAINTEXT? (no E2E on this leg)")
print("=" * 70)
print(f"Raw bytes as codec data: {encrypted[:32].hex()}")
b0 = encrypted[0]
print(f"  First byte: 0x{b0:02x} ({b0:08b}) bit7={'CELT' if (b0&0x80) else 'SILK'}")
print(f"  Opus-like TOC? {(b0 & 0xFC) in (0xF8,0xF0,0xE0,0xC0,0x80,0x00)}")

print()
print("=" * 70)
print("STEP 9: Try all IV combos — SSRC/seq at different byte offsets")
print("=" * 70)
for ssrc_off in [4, 8]:
    for seq_off in [2, 4, 6]:
        ssrc = struct.unpack("!I", FRAME_BYTES[ssrc_off:ssrc_off+4])[0]
        seq = struct.unpack("!H", FRAME_BYTES[seq_off:seq_off+2])[0]
        iv = generate_iv(session_salt, ssrc, seq)
        dec = _aes_ctr(session_key, iv, encrypted)
        opus_like = (dec[0] & 0xFC) in (0xF8,0xF0,0xE0,0xC0,0x80,0x00)
        mlow_celt = (dec[0] & 0x80) == 0x80
        print(f"  ssrc@[{ssrc_off:1d}]={ssrc:08x} seq@[{seq_off:1d}]={seq:5d} → "
              f"dec[0]=0x{dec[0]:02x} opus={opus_like} mlow={mlow_celt}")

print()
print("=" * 70)
print("STEP 10: HBH→E2E layered decrypt (real hbh_key from log)")
print("=" * 70)

# Frame #2: 9078000100015cc0a50d9871debe0002d3000043800000009702e18ed2caf4e81a5f53e5c86fe9bbcb779f46a85511f2
FRAME2_HEX = "9078000100015cc0a50d9871debe0002d3000043800000009702e18ed2caf4e81a5f53e5c86fe9bbcb779f46a85511f2"
FRAME2 = bytes.fromhex(FRAME2_HEX)
FRAME2_SSRC = 0xa50d9871
FRAME2_SEQ = 0x0001

# This call's keys
CK2 = bytes.fromhex("95a67af8a9218e61a32461783e665350a458dec2897431bd26510c3442d08369")
RECV_MK2 = bytes.fromhex("a0dd6ac38f9ccf332f1a6d7fdd60daca")
RECV_MS2 = bytes.fromhex("3735781f2bc002f6aad2893695d3")
HBH_KEY = bytes.fromhex("93343fed7180f58d3834d7ccad4943404768fa6462caf548c5eb2c4b7877")

# Parse frame #2
flags2 = (FRAME2[14] << 8) | FRAME2[15]
hdr2 = 20 if (flags2 & 1) else 16
enc2 = FRAME2[hdr2:-4]
mi2 = FRAME2[-4:]
print(f"Frame #2: seq={FRAME2_SEQ} ssrc=0x{FRAME2_SSRC:08x} hdr={hdr2}B enc={len(enc2)}B mi={mi2.hex()}")

# Derive E2E recv session keys for this call
sk2 = derive_srtp_key(RECV_MK2, RECV_MS2, SRTP_LABEL_ENCRYPTION, 16)
ss2 = derive_srtp_key(RECV_MK2, RECV_MS2, SRTP_LABEL_SALT, 14)
print(f"E2E session_key: {sk2.hex()}")
print(f"E2E session_salt: {ss2.hex()}")

# ── Step 10a: Plain E2E decrypt (what code currently does) ──
iv_e2e = generate_iv(ss2, FRAME2_SSRC, FRAME2_SEQ)
dec_e2e = _aes_ctr(sk2, iv_e2e, enc2)
print(f"E2E only decrypt ({len(dec_e2e)}B): {dec_e2e.hex()}")
print(f"  First byte: 0x{dec_e2e[0]:02x}")

# ── Step 10b: HBH decrypt first, then E2E ──
# HBH context: hbh_key[0:16]=master_key, hbh_key[16:30]=master_salt, hbh=True
hbh_mk = HBH_KEY[:16]
hbh_ms = HBH_KEY[16:30]
hbh_sk = derive_srtp_key(hbh_mk, hbh_ms, SRTP_LABEL_ENCRYPTION, 16)
hbh_ss = derive_srtp_key(hbh_mk, hbh_ms, SRTP_LABEL_SALT, 14)
print(f"\nHBH session_key: {hbh_sk.hex()}")
print(f"HBH session_salt: {hbh_ss.hex()}")

# HBH IV: hbh=True means iv[8:16] ^= (packetIndex << 16) [64-bit]
def generate_iv_hbh(salt, ssrc, index):
    iv = bytearray(16)
    iv[:14] = salt[:14]
    ssrc_bytes = struct.pack("!I", ssrc)
    for i in range(4):
        iv[4 + i] ^= ssrc_bytes[i]
    shifted = (index & 0xFFFFFFFFFFFF) << 16
    idx_bytes = struct.pack("!Q", shifted)
    for i in range(8):
        iv[8 + i] ^= idx_bytes[i]
    return bytes(iv)

# Try HBH decrypt of the payload (treating payload as HBH-encrypted E2E frame)
iv_hbh = generate_iv_hbh(hbh_ss, FRAME2_SSRC, FRAME2_SEQ)
dec_hbh = _aes_ctr(hbh_sk, iv_hbh, enc2)
print(f"HBH decrypt ({len(dec_hbh)}B): {dec_hbh[:32].hex()}")
print(f"  First byte: 0x{dec_hbh[0]:02x}")

# Now try E2E decrypt of HBH output
# HBH-decrypted data should be: RTP_header(12B) + E2E_encrypted + SRTP_auth(4B)
# OR it could be just E2E_encrypted + MI
# Try treating it as standard SRTP (RTP header + encrypted + auth)
if len(dec_hbh) >= 16:
    rtp_v = (dec_hbh[0] >> 6) & 3
    rtp_pt = dec_hbh[1] & 0x7F
    rtp_ssrc = struct.unpack("!I", dec_hbh[8:12])[0]
    print(f"  As RTP: V={rtp_v} PT={rtp_pt} SSRC=0x{rtp_ssrc:08x}")
    if rtp_v == 2:
        rtp_hdr_sz = 12
        inner_enc = dec_hbh[rtp_hdr_sz:-4]
        inner_auth = dec_hbh[-4:] if len(dec_hbh) >= rtp_hdr_sz + 4 else b""
        print(f"  Inner RTP: payload={len(inner_enc)}B auth={inner_auth.hex()}")
        if len(inner_enc) > 0:
            iv_inner = generate_iv(ss2, rtp_ssrc, FRAME2_SEQ)
            dec_inner = _aes_ctr(sk2, iv_inner, inner_enc)
            print(f"  HBH→RTP→E2E decrypt: {dec_inner[:32].hex()}")
            print(f"    First byte: 0x{dec_inner[0]:02x}")

# Also try: HBH decrypt on FULL frame (not just payload)
iv_hbh_full = generate_iv_hbh(hbh_ss, FRAME2_SSRC, FRAME2_SEQ)
dec_hbh_full = _aes_ctr(hbh_sk, iv_hbh_full, FRAME2)
print(f"\nHBH on full frame: {dec_hbh_full[:32].hex()}")

# Try various offsets for HBH decrypt
for off in [0, 2, 4, 8, hdr2]:
    if off + 1 < len(FRAME2):
        iv_h = generate_iv_hbh(hbh_ss, FRAME2_SSRC, FRAME2_SEQ)
        dec_h = _aes_ctr(hbh_sk, iv_h, FRAME2[off:])
        print(f"  HBH from offset {off}: {dec_h[:16].hex()}")
# HBH key from log: 30 bytes
HBH_KEY_HEX = "48b889bd8c72dbd30c94d8b06aaabc8d362ca7881c68dbcd7c23a5fe"
# Wait — we need the actual HBH key. Let's use a placeholder and try common patterns.

# Actually, let me check: the HBH key in the log is 30 bytes.
# From relay ack parsing: hbh_key is raw bytes from <hbh_key> node.
# The HBH context uses: master_key = hbh_key[:16], master_salt = hbh_key[16:30]? 
# Or maybe hbh_key is the raw key for a different cipher.

# Let's try: treat the encrypted data as needing HBH decrypt with various key interpretations
# The hbh_key is 30 bytes — could be AES-256 key (32B? no, 30B)
# Could be: key[0:16]=AES_key, key[16:30]=salt (14B)

# Actually, for HBH, let me re-read our SrtpContext init:
# In call_manager: SrtpContext(master_key, master_salt, hbh=True)
# hbh=True means use HBH IV format: iv[8:16] ^= (packetIndex << 16)

# For primary device relay, the HBH might use a different key than SRTP.
# The hbh_key from relay ack might be the raw AES key.

print("HBH key hint: the relay ack provides a 30-byte hbh_key")
print("Trying: HBH_decrypt(E2E_payload) with hbh_key as AES-128 key")
print("(We need the actual hbh_key from the log — using placeholder for now)")

print()
print("=" * 70)
print("STEP 11: Try WITHOUT the last 4 bytes (maybe no MI tag on this protocol)")
print("=" * 70)
# What if the frame has NO MI tag and the last 4 bytes are part of encrypted data?
full_enc = FRAME_BYTES[16:]  # all bytes after 16B header
iv_full = generate_iv(session_salt, FRAME_SSRC, FRAME_SEQ)
dec_full = _aes_ctr(session_key, iv_full, full_enc)
print(f"Decrypt ALL {len(full_enc)}B after header: {dec_full[:32].hex()}")
print(f"  First byte: 0x{dec_full[0]:02x}")

# Try with 8-byte header (like 8FCE format but for 9078)
enc8 = FRAME_BYTES[8:]  # skip only 8 bytes
iv8 = generate_iv(session_salt, FRAME_SSRC, FRAME_SEQ)
dec8 = _aes_ctr(session_key, iv8, enc8)
print(f"Decrypt from byte 8 ({len(enc8)}B): {dec8[:32].hex()}")
print(f"  First byte: 0x{dec8[0]:02x}")

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print("HKDF derivation: CORRECT (master_key, master_salt match)")
print("warp_auth_key: CORRECT")
print("WARP MI tag: MISMATCH (relay rewrites it)")
print("E2E decrypt: ALL key variants produce garbage")
print("IV offset variations: ALL produce garbage")
print("Plaintext hypothesis: NOT plaintext")
print()
print("HYPOTHESIS: Raw UDP relay path wraps everything in HBH encryption.")
print("We need the actual hbh_key from relay ack to test this.")

print()
print("=" * 70)
print("STEP 12: SFrame (AES-128-GCM) — the MISSING inner layer!")
print("=" * 70)

def derive_sframe_key(call_key, participant_id):
    if participant_id.endswith("@lid") and ":" not in participant_id.split("@")[0]:
        participant_id = participant_id.split("@")[0] + ":0@lid"
    info = b"e2e sframe key" + participant_id.encode()
    prk = hmac.new(call_key[0:16], call_key[16:32], hashlib.sha256).digest()
    okm, t, i = b"", b"", 1
    while len(okm) < 32:
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        okm += t; i += 1
    return okm[:32]

sf_key_phone = derive_sframe_key(CK2, "248846345101511:0@lid")
sf_key_us = derive_sframe_key(CK2, "34197200736283:0@lid")
print(f"SFrame key (phone): {sf_key_phone.hex()}")
print(f"SFrame key (us):    {sf_key_us.hex()}")

# E2E-decrypted output from frame #2 of new call
# (we need to recompute since dec_e2e was overwritten)
# Actually, let's use the E2E decrypt we did in step 10
# e2e_output from step 10: "1c00185b94f70f5a863e786043d254704d78ae67cbc965e892bd48a6"
e2e_frame2 = bytes.fromhex("1c00185b94f70f5a863e786043d254704d78ae67cbc965e892bd48a6")
print(f"\nE2E decrypted (28B): {e2e_frame2.hex()}")

for label, sf_key in [("phone", sf_key_phone), ("us", sf_key_us)]:
    print(f"\nSFrame decrypt with {label} key:")
    b0 = e2e_frame2[0]
    ver = (b0 >> 6) & 3; kid = (b0 >> 4) & 3; ctl = b0 & 0x0F; ctr_len = ctl + 1
    print(f"  ver={ver} KID={kid} ctr_len={ctr_len}")
    if ver != 0: print("  Bad version"); continue
    if len(e2e_frame2) < 1 + ctr_len + 16: print("  Too short"); continue
    ctr = e2e_frame2[1:1+ctr_len]
    ct = e2e_frame2[1+ctr_len:-16]
    tag = e2e_frame2[-16:]
    nonce = b'\x00' * (12 - ctr_len) + ctr
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        pt = AESGCM(sf_key).decrypt(nonce, ct + tag, bytes([b0]))
        print(f"  SUCCESS! plaintext({len(pt)}B): {pt.hex()}")
        print(f"    First byte: 0x{pt[0]:02x}")
    except Exception as e:
        print(f"  FAIL: {e}")
