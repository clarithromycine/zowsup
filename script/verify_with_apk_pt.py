"""Verify: encrypt APK's ID8.A06 plaintext with our encryption cert, check round-trip."""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.layer.canonical_credentials import encrypt_with_cert, decrypt_response
from Crypto.PublicKey import RSA

# ── APK's ID8.A06 plaintext (hex from Frida) ──
apk_pt_hex = "7b2276657273696f6e223a312c2274696d657374616d70223a313738343236303330372c2270617373776f7264223a22235057445f57413a31313a313738343236303330373a4153346f7267386d6d6167726a464c735070414141563051773031696c5349705f456f7353344d576232316e304f6b35726c782d3639613161463375795575572d53644942345850316946725061534e5a6c6679556e66315372582d6a76344a4841304863305a394a685349764953637941537346624438737873515848614c5a476a756355434276454159355a45486346737872357276616d42656561756c3750483845705068666633477078347639517a726737577a544d766744795f5a70567461657a48345a5250624f615f6955464576514f695f627956347947765044477078335a38466254444b5757754869513979456464546b6b6d735048517a696d76395849455f3247385f31484d77316a6b6a44655179655f5477694e50593039336f4251544a7776623056307947327937316d702d357a432d7742706f686d31575654736b45613673517848332d4e4458522d376931735f33544c784f4965672d45686f4c474d73635a564661314b694156425a3867674666767a6b4c3242336b7973654558556951764470756855554c374b7a4a55446c625645784b4f346d39497748324d78335f6c486250655a615834626c4641714a497a2d684b79597455222c22636c69656e745f7075625f6b6579223a222d2d2d2d2d424547494e205055424c4943204b45592d2d2d2d2d5c6e4d494942496a414e42676b71686b6947397730424151454641414f43415138414d49494243674b4341514541375a754d57734556627444734742326e5831516177455164362b796e3853334b7432464f537a69535368395a4f79483266713673594d7370577546674551426e6b75576f75737a70563579725742573033367665484c32466a444649734269504a52756d30495065674262386e697330676f6a55724f7456336e47684e6930376e3857654f526b5a6757724a663932575a766d7250413168304d4b3376483864532b444e4f4561436f6b5137506d6931516f702b663368456747306456654442773862586651625874794c7943744963617838724b716e357077393441616a6f4d72686d42506f432b774e36786c592b534a6a2b303552453036562b78417334525061624772517462384f39594f4f6a3846786e4a62682b774f336e77755343516e7631436274424b71344d764b72756c3743497774564e585a666c394c304d4f5771726d38786652554437722b716778474d3259774944415141425c6e2d2d2d2d2d454e44205055424c4943204b45592d2d2d2d2d5c6e222c22636c69656e745f7075625f6b65795f74797065223a225253412032303438227d"

apk_plaintext = bytes.fromhex(apk_pt_hex).decode("utf-8")
print(f"APK plaintext: {len(apk_plaintext)} chars")
print(f"APK plaintext preview: {apk_plaintext[:100]}...")

# ── Use the encryption cert from GetCertificates ──
# The user should paste the encryption_pem here
encryption_pem = """-----BEGIN CERTIFICATE-----
MIID... (paste your encryption_pem here)
-----END CERTIFICATE-----"""

# For now, generate a self-signed cert for testing
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa as crypto_rsa
from cryptography.x509 import (
    CertificateBuilder, Name, NameAttribute, BasicConstraints, random_serial_number,
)
import datetime as dt

crypto_key = crypto_rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
private_key = RSA.import_key(crypto_key.private_bytes(
    serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
))
subject = issuer = Name([
    NameAttribute(NameOID.COUNTRY_NAME, "US"),
    NameAttribute(NameOID.ORGANIZATION_NAME, "Test"),
    NameAttribute(NameOID.COMMON_NAME, "test.local"),
])
cert_builder = CertificateBuilder().subject_name(subject).issuer_name(issuer)
cert_builder = cert_builder.public_key(crypto_key.public_key())
cert_builder = cert_builder.serial_number(random_serial_number())
cert_builder = cert_builder.not_valid_before(dt.datetime.now(dt.timezone.utc))
cert_builder = cert_builder.not_valid_after(dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1))
cert_builder = cert_builder.add_extension(BasicConstraints(ca=False, path_length=None), critical=True)
cert = cert_builder.sign(private_key=crypto_key, algorithm=hashes.SHA256(), backend=default_backend())
encryption_pem = cert.public_bytes(serialization.Encoding.PEM).decode()

# ── Encrypt APK's plaintext with our encrypt_with_cert ──
enc_key, ctxt, tag, iv = encrypt_with_cert(apk_plaintext, encryption_pem)
print(f"\nOur encrypt_with_cert output:")
print(f"  enc_key: {len(enc_key)}B")
print(f"  data:    {len(ctxt)}B")
print(f"  tag:     {len(tag)}B")
print(f"  nonce:   {len(iv)}B")

# ── Verify: decrypt and check round-trip ──
decrypted = decrypt_response(enc_key, ctxt, tag, iv, private_key)
if decrypted == apk_plaintext:
    print(f"\n✓ ROUND-TRIP SUCCESS: decrypt(encrypt(apk_plaintext)) == apk_plaintext")
else:
    print(f"\n✗ ROUND-TRIP FAILED!")
    for i, (a, b) in enumerate(zip(decrypted, apk_plaintext)):
        if a != b:
            print(f"  First diff at pos {i}: {repr(a)} vs {repr(b)}")
            break

# ── Parse and show the APK plaintext structure ──
pt_json = json.loads(apk_plaintext)
print(f"\nAPK plaintext JSON fields:")
print(f"  version: {pt_json['version']}")
print(f"  timestamp: {pt_json['timestamp']} (len={len(str(pt_json['timestamp']))})")
print(f"  password: {pt_json['password'][:60]}... (len={len(pt_json['password'])})")
print(f"  client_pub_key: {pt_json['client_pub_key'][:50]}... (len={len(pt_json['client_pub_key'])})")
print(f"  client_pub_key_type: {pt_json['client_pub_key_type']}")
