"""Calculate exact plaintext component lengths to find 4-byte difference."""

# Real device plaintext = 1028 bytes (from decrypted data length)
# Our plaintext = 1024 bytes

# Fixed parts of the plaintext JSON:
# {"version":1,"timestamp":NNNNNNNNNN,"password":"#PWD_WA:11:NNNNNNNNNN:BBB...BBB","client_pub_key":"-----BEGIN PUBLIC KEY-----\nPPPP...PPPP\n-----END PUBLIC KEY-----\n","client_pub_key_type":"RSA 2048"}

# Let's compute each part exactly
ts = "1784171208"  # example 10-digit timestamp

# Header part 1 (before password value)
h1 = '{"version":1,"timestamp":' + ts + ',"password":"#PWD_WA:11:' + ts + ':'
print(f"h1: {len(h1)} chars = {h1}")

# PWD_WA blob in urlsafe b64:
# Blob structure: [1][key_id][iv:12][enc_key_len:2 LE][enc_key:256][tag:16][password_ctxt:50]
# For our password length of 50: 1+1+12+2+256+16+50 = 338 bytes
# urlsafe base64 (no pad): ceil(338*4/3) = 451 chars

# For password length of 53: 1+1+12+2+256+16+53 = 341 bytes
# urlsafe base64 (no pad): ceil(341*4/3) = 455 chars
# Difference in b64: 4 chars = 4 bytes in JSON!

# For password length of 54: 1+1+12+2+256+16+54 = 342 bytes
# urlsafe base64 (no pad): ceil(342*4/3) = 456 chars
# Difference: 5 chars

print()
for pwd_len in [50, 51, 52, 53, 54, 55]:
    blob_len = 1 + 1 + 12 + 2 + 256 + 16 + pwd_len
    b64_len = (blob_len * 4 + 2) // 3  # ceil division for base64
    print(f"password_len={pwd_len}: blob={blob_len}B, urlsafe_b64={b64_len} chars")

# Tail part
tail = '","client_pub_key":"-----BEGIN PUBLIC KEY-----\\n'
print(f"\ntail header: {len(tail)} chars")

# DER public key in base64 (RSA 2048 = 294 bytes DER → 392 base64 chars)
pub_b64_len = 392
print(f"pubkey b64: {pub_b64_len} chars")

# Footer
footer = '\\n-----END PUBLIC KEY-----\\n","client_pub_key_type":"RSA 2048"}'
print(f"footer: {len(footer)} chars")

# Total for password_len=50
total_50 = len(h1) + 451 + len(tail) + pub_b64_len + len(footer)
print(f"\nTotal with pwd_len=50: {total_50} bytes")

# Total for password_len=53  
total_53 = len(h1) + 455 + len(tail) + pub_b64_len + len(footer)
diff = total_53 - total_50
print(f"Total with pwd_len=53: {total_53} bytes (diff: {diff})")

print(f"\nReal device: 1028 bytes")
print(f"Our code: {total_50} bytes (our log says 1024)")
print(f"Real - Ours = {1028 - total_50} bytes")
