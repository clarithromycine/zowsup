"""
Decrypt WhatsApp primary-device 9079 audio frames using SRTP key derivation.

Uses zowsup's voip.media.encryption module (matches wacalls srtp.go exactly).

Usage:
  python script/decrypt_audio.py <enc_key_hex> <device_jid> <ssrc> <frame_hex>
  
  enc_key_hex: 64 hex chars (32 bytes) — from signaling EncryptionKey
  device_jid:  your JID, e.g. "60139549324:0@s.whatsapp.net"
  ssrc:        decimal SSRC, e.g. 3429896866
  frame_hex:   9079 frame hex (space-separated)

Example:
  python script/decrypt_audio.py abc123... "60139549324@s.whatsapp.net" 3429896866 "90790001 0000..."
"""
import sys
import struct

# Add zowsup root to path
sys.path.insert(0, ".")

from voip.media.encryption import (
    derive_per_jid_srtp_key,
    SrtpContext,
)


def parse_9079_frame(data: bytes) -> dict:
    """Parse primary device 9079 audio frame header."""
    if len(data) < 20:
        return None
    frame_type = struct.unpack(">H", data[0:2])[0]
    seq = struct.unpack(">H", data[2:4])[0]
    timestamp = struct.unpack(">I", data[4:8])[0]
    session_id = struct.unpack(">I", data[8:12])[0]
    sub_type = struct.unpack(">H", data[12:14])[0]
    flags = struct.unpack(">H", data[14:16])[0]
    field1 = struct.unpack(">H", data[16:18])[0]
    field2 = struct.unpack(">H", data[18:20])[0]
    extra_header = data[20:24] if len(data) > 24 else b""
    payload_start = 20 + len(extra_header)
    payload = data[payload_start:] if len(data) > payload_start else b""
    
    return {
        "frame_type": f"0x{frame_type:04x}",
        "seq": seq,
        "timestamp": timestamp,
        "session_id": f"0x{session_id:08x}",
        "sub_type": sub_type,
        "flags": f"0x{flags:04x}",
        "field1": f"0x{field1:04x}",
        "field2": f"0x{field2:04x}",
        "extra_header": extra_header,
        "payload": payload,
        "header_len": payload_start,
    }


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        return
    
    enc_key_hex = sys.argv[1]
    device_jid = sys.argv[2]
    ssrc = int(sys.argv[3])
    frame_hex = sys.argv[4].replace(" ", "")
    
    enc_key = bytes.fromhex(enc_key_hex)
    if len(enc_key) != 32:
        print(f"ERROR: enc_key must be 32 bytes (64 hex chars), got {len(enc_key)}")
        return
    
    frame_data = bytes.fromhex(frame_hex)
    parsed = parse_9079_frame(frame_data)
    if not parsed:
        print("ERROR: frame too short")
        return
    
    print(f"callKey: {enc_key.hex()}")
    print(f"deviceJid: {device_jid}")
    print(f"SSRC: {ssrc} (0x{ssrc:08x})")
    
    print(f"\nFrame ({len(frame_data)}B):")
    for k, v in parsed.items():
        if k in ("payload", "extra_header"):
            print(f"  {k}: {v.hex()} ({len(v)}B)")
        else:
            print(f"  {k}: {v}")
    
    # Derive keys & decrypt
    km = derive_per_jid_srtp_key(enc_key, device_jid)
    ctx = SrtpContext(km)
    
    print(f"\nDerived keys:")
    print(f"  sessionKey:  {ctx.session_key.hex()}")
    print(f"  sessionSalt: {ctx.session_salt.hex()}")
    
    payload = parsed["payload"]
    if len(payload) == 0:
        print("\nNo payload to decrypt")
        return
    
    decrypted = ctx.decrypt(ssrc, parsed["seq"], payload)
    
    print(f"\nDecrypted ({len(decrypted)}B):")
    print(f"  hex: {decrypted.hex()}")
    
    if len(decrypted) > 0:
        toc = decrypted[0]
        config = (toc >> 3) & 0x1F
        stereo = (toc >> 2) & 1
        mode = toc & 3
        print(f"  TOC=0x{toc:02x} config={config} stereo={stereo} mode={mode}")
        if 0 <= config <= 30:
            print(f"  ✅ Looks like valid Opus!")
        else:
            print(f"  ❌ Not Opus — wrong key or format?")


if __name__ == "__main__":
    main()
