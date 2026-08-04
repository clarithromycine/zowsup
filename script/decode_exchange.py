"""Decode our exchange query hex and compare structure with real device."""
import json

# Our exchange query hex from log (first part)
our_hex = (
    "7b2271756572794964223a223235373237313837313630323033363230222c227661726961626c6573223a7b22696e70757422"
    "3a7b22656e637279707465645f70617373776f7264223a7b22616c676f726974686d223a2272736132303438222c226461746122"
    "3a2259736d72453879536c68366c79644f6730642f635772654665326a46336b4858536a394a554d505a7a31434c66756d4c3169"
    "6734723069652f57444e77627246777932623153302f784e335c6e426f67654536612b5448584f7a4532317035786c596b327164"
    "6764334861365445754159726163326b2b2b6b78486b325149704f712b5a476e76796b466c69463843676c547a427433626d6a5c"
    "6e704833576c6931534f5863484e6e5238586e4f6643622f714f5039306e6e7044755661585841417530654c6d4c507159446b30"
    "513553633337634b7a5a416a6d486975695161616f4a2b61415c6e424436476b3949586c4857442f46566c572b49593267514e62"
    "2f653449414679766e3445396a7451685756437648324d6152396e64443765634f37723666306a4b444d5847312f43765235685c"
    "6e415a7874462b656e4e764362466d6a3936654841386953304a6a3843734d416b30554a396474366446434e52796f6b5941586f"
    "593739446d71313361366f485a51457a7054542f49356170585c6e7330657267"
)

our_json = bytes.fromhex(our_hex).decode()
print("=== Our Exchange Query (decoded) ===")
print(our_json[:200])
print("...")
print()

# Parse and show structure
parsed = json.loads(our_json)
inp = parsed["variables"]["input"]
ep = inp["encrypted_password"]

print("Top-level keys:", list(parsed.keys()))
print("input keys:", list(inp.keys()))
print("encrypted_password keys:", list(ep.keys()))
print()
print("algorithm:", ep["algorithm"])
print("nonce (top-level) length:", len(inp["nonce"]))
print("registration_trace_id:", inp["registration_trace_id"])
print()

# Check data field for \n chars
for k in ["data", "key", "nonce", "tag"]:
    v = ep[k]
    print(f"ep.{k}: len={len(v)}, has final \\n: {v.endswith(chr(10))}, last 3 chars: {repr(v[-3:])}")

print()
print("=== Real Device Exchange Structure (for comparison) ===")
print("Top-level keys: ['queryId', 'variables']")
print("input keys: ['encrypted_password', 'nonce', 'registration_trace_id', 'request_id', 'use_case']")
print("encrypted_password keys: ['algorithm', 'data', 'key', 'nonce', 'tag']")
print()

# Compare
print("=== Comparison ===")
print("Top-level keys match:", list(parsed.keys()) == ['queryId', 'variables'])
print("input keys match:", list(inp.keys()) == ['encrypted_password', 'nonce', 'registration_trace_id', 'request_id', 'use_case'])
print("ep keys match:", list(ep.keys()) == ['algorithm', 'data', 'key', 'nonce', 'tag'])
print("algorithm value:", ep["algorithm"] == "rsa2048")
