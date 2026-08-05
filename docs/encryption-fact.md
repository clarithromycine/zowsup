# Pair-Device Encryption — Verified Facts & Bug Analysis

> **Date**: 2026-07-23
> **Source**: APK `IO1.A01` (classes9.dex) decompiled source + real-device packet capture
> **Scope**: `<pem>` and `<encryption-metadata>` fields in pair-device IQ

---

## 1. APK Source — `IO1.A01` Key Variables

### 1.1 `C40471Hst` fields (pairing state container)

| Field | Source | Description |
|-------|--------|-------------|
| `A00` | `c40783HyT` | Companion identity key pair |
| `A01` | `enumC25747BdB` | E2EE type (device type) |
| `A05` | `str` (QR ref) | QR ref string |
| `A06` | `bArr2 = idx.A05` | **adv_secret** (QR field 4, 32 bytes) |
| `A07` | `bArr` | **priorAttemptKey** — `C1V0.A00(priorAttemptSecret, AbstractC39743HfY.A00, 32)` or `null` |
| `A08` | `bArr3 = idx.A06` | priorAttemptSecret (raw, from QR or null) |

### 1.2 `priorAttemptKey` derivation (`A05` method)

```java
byte[] bArr3 = idx.A06;  // priorAttemptSecret
if (bArr3 != null) {
    bArr = C1V0.A00(bArr3, AbstractC39743HfY.A00, 32);  // HKDF-Extract
} else {
    bArr = null;  // first pairing attempt — no prior secret
}
```

**For first pairing attempt**: `priorAttemptSecret = null` → `c40471Hst.A07 = null`.

---

## 2. `<pem>` Field — secretKey Derivation (VERIFIED)

### 2.1 APK code

```java
final SecretKeySpec secretKeySpec = new SecretKeySpec(
    C1V0.A02(bArr4, c40471Hst.A07, IJW.A00, 32),
    "AES-GCM"
);
```

Where:
- `bArr4 = c40471Hst.A06` = **adv_secret** (QR field 4)
- `c40471Hst.A07` = **priorAttemptKey** (null for first pairing)
- `IJW.A00` = `"Canonical Ent Companion Nonce Encrypt".getBytes()` (confirmed by user)
- `C1V0.A02` = HKDF-Extract-and-Expand

### 2.2 Correct formula

```
secretKey = HKDF-SHA256(
    ikm   = adv_secret,
    salt  = priorAttemptKey,       // null for first pairing → HKDF uses zero-byte salt
    info  = "Canonical Ent Companion Nonce Encrypt",
    L     = 32
)
```

### 2.3 XML serialization

```java
A0s.A03(new C08730bL("pem", secretKey.getEncoded(), null));
```

`secretKey.getEncoded()` = raw 32 bytes. Sent as **raw bytes** in ProtocolTreeNode data.
Log display shows base64 (e.g. `GcUZRNkj752G6lia8GlbdUhrEmTGdT1WajvNhHOGhlQ=` = 32 bytes).

### 2.4 Other `<pem>` sub-fields

```java
A0s.A03(new C08730bL("ttl", {new C08710bJ("ts_s", TimeUnit.DAYS.toSeconds(5L))}));
A0s.A03(new C08730bL("key_id", "1", null));
```

- `<ttl ts_s="432000"/>` — 5 days in seconds (attribute, not data)
- `<key_id>1</key_id>` — string "1" (text data)

---

## 3. `<encryption-metadata>` Field — AuthProofHelper (VERIFIED)

### 3.1 APK code — AuthProofHelper invocation

```java
C32872Eg5 c32872Eg5 = (C32872Eg5) io1.A0L.get();  // AuthProofHelper
C28161Oc c28161Oc = certificate_from_store;        // encryption cert
C33089Ejm c33089Ejm = cert_validation_result;
//   .A00 = password PEM data
//   .A01 = PublicKey (password public key)
//   .A02 = key_id

str2 = GH1.A01(publicKey);  // PEM string of password public key
c33581Es2 = c32872Eg5.A01(c28161Oc, c33089Ejm.A00, str2, c33089Ejm.A02);
```

### 3.2 AuthProofHelper.A01 logic (from docs/wwwcreateuser-debug-progress.md)

```
1. Read stored canonical password (from CanonicalEntCredentials)
2. Build PWD_WA hash: ID8.A02(key_id, stored_password, null, password_pubkey)
   → "#PWD_WA:11:{timestamp}:{urlsafe_b64_blob}"
3. Build plaintext JSON:
   {"version":1, "timestamp":ts, "password":PWD_WA_hash,
    "client_pub_key":password_pubkey_PEM, "client_pub_key_type":"RSA 2048"}
4. Encrypt plaintext: ID8.A06(json, encryption_cert)
   → AES-GCM + RSA-OAEP(SHA1) → {encrypted_key, ciphertext, tag, iv}
```

### 3.3 Key insight: encryption-metadata uses STORED canonical password, NOT adv_secret

The `encryption-metadata` is a **proof of canonical identity**:
- **password** = PWD_WA hash of the **stored canonical password** (from WWWCreateUser/WWWExchangeNonceForAccessToken)
- **client_pub_key** = PEM of the **password public key** from the certificate (password_pem)
- Encrypted with the **encryption_pem** certificate

This is NOT related to adv_secret at all. The adv_secret is only used for:
1. The `<pem>` secretKey derivation (HKDF)
2. The device-identity HMAC

### 3.4 C33581Es2 field mapping to XML

| C33581Es2 field | XML tag | Content |
|-----------------|---------|---------|
| A02 | `<encrypted_key>` | RSA-OAEP encrypted AES key (raw bytes) |
| A03 | `<nonce>` | AES-GCM IV (raw bytes) |
| A01 | `<encrypted_data>` | AES-GCM ciphertext (raw bytes) |
| A00 | `<auth_tag>` | AES-GCM auth tag (raw bytes) |

All sent as **raw bytes** in ProtocolTreeNode data. Log shows base64.

### 3.5 XML structure

```xml
<encryption-metadata version="1" algorithm="rsa2048">
  <encrypted_key>{raw RSA-OAEP bytes}</encrypted_key>
  <nonce>{raw 12-byte IV}</nonce>
  <encrypted_data>{raw AES-GCM ciphertext}</encrypted_data>
  <auth_tag>{raw 16-byte GCM tag}</auth_tag>
</encryption-metadata>
```

---

## 4. BUGS in Current Implementation

### BUG-A: `<pem>` secretKey salt is wrong

**Current** (`qr_crypto.py` `derive_secret_key`):
```python
secret_key = HKDF(ikm=adv_secret, salt=companion_noise_pub, info="Canonical Ent Companion Nonce Encrypt", L=32)
```

**Correct** (APK):
```python
secret_key = HKDF(ikm=adv_secret, salt=priorAttemptKey_or_null, info="Canonical Ent Companion Nonce Encrypt", L=32)
```

For first pairing: `priorAttemptKey = None` → HKDF uses zero-byte salt (32 zeros).
Current code incorrectly uses `companion_noise_pub` as salt.

**Fix**: `derive_secret_key(adv_secret, salt=None)` for first pairing.

---

### BUG-B: `<pem>` data is base64-encoded (should be raw bytes)

**Current** (`iq_md_pair_device.py`):
```python
pemNode.addChild(ProtocolTreeNode("pem", {}, None, base64.b64encode(self.secretKey)))
```

**Correct** (APK sends `secretKey.getEncoded()` = raw bytes):
```python
pemNode.addChild(ProtocolTreeNode("pem", {}, None, self.secretKey))
```

The binary encoder sends raw bytes directly. Log display shows base64, but the wire format is raw bytes.

---

### BUG-C: `<encryption-metadata>` fields are base64-encoded (should be raw bytes)

**Current** (`iq_md_pair_device.py`):
```python
encNode.addChild(ProtocolTreeNode("encrypted_key", {}, None,
    base64.b64encode(self.encryptionMetadata["encrypted_key"])))
# Same for nonce, encrypted_data, auth_tag
```

**Correct** (APK sends raw bytes):
```python
encNode.addChild(ProtocolTreeNode("encrypted_key", {}, None,
    self.encryptionMetadata["encrypted_key"]))
# Same for nonce, encrypted_data, auth_tag
```

---

### BUG-D: encryption-metadata password uses adv_secret instead of stored canonical password

**Current** (`md_link.py`):
```python
password_hash = build_password_hash(
    adv_secret=adv_secret,  # WRONG — using adv_secret as the "password"
    key_type=0,
    client_rsa_pubkey=rsa_key,
    timestamp=params_v2["key_index_ts"],
)
```

**Correct** (APK AuthProofHelper.A01):
```python
pwd_hash = build_pwd_wa_hash(
    password=stored_canonical_password,  # from WWWExchangeNonceForAccessToken
    key_id=password_pem_key_id,
    pubkey_pem=password_pem,
    timestamp=ts,
)
```

The encryption-metadata is a proof of canonical identity. It uses the **stored canonical password** (WaFbPassword), NOT adv_secret.

---

### BUG-E: encryption-metadata client_pub_key uses new RSA key instead of password_pem

**Current** (`md_link.py`):
```python
rsa_key = generate_rsa_keypair()
client_pub_key_pem = rsa_pubkey_to_pem(rsa_key)
# ... used in plaintext JSON
```

**Correct** (APK AuthProofHelper.A01):
```python
client_pub_key = password_pem  # PEM string of password public key from certificate
```

The `client_pub_key` in the plaintext JSON is the **password_pem** (the PEM string of the password public key from the canonical certificate), NOT a newly generated RSA key.

---

### BUG-F: encryption-metadata PWD_WA hash uses wrong RSA public key

**Current** (`qr_crypto.py` `build_password_hash`):
```python
# Uses client_rsa_pubkey (newly generated) for RSA/PKCS1 encryption
rsa_cipher = PKCS1_v1_5.new(client_rsa_pubkey)
encrypted_key = rsa_cipher.encrypt(aes_key)
```

**Correct** (APK ID8.A02):
```python
# Uses password_pem (certificate's password public key) for RSA/PKCS1 encryption
rsa_pub = RSA.import_key(password_pem)
encrypted_key = PKCS1_v1_5.new(rsa_pub).encrypt(aes_key)
```

The PWD_WA hash encrypts the AES key with the **password_pem** public key, not a newly generated RSA key.

---

### BUG-G: encryption-metadata uses `build_password_hash` instead of `build_pwd_wa_hash`

**Current** (`md_link.py`):
Uses `build_password_hash` from `qr_crypto.py` which:
- Takes `adv_secret` as the password to encrypt
- Uses `key_type` parameter (not `key_id`)
- Uses `client_rsa_pubkey` for RSA encryption

**Correct**:
Should use `build_pwd_wa_hash` from `canonical_credentials.py` which:
- Takes the stored canonical password as the password to encrypt
- Uses `key_id` parameter
- Uses `password_pem` for RSA encryption
- Uses the same PWD_WA format: `#PWD_WA:11:{timestamp}:{urlsafe_b64_blob}`

---

## 5. Already-Confirmed-Correct Algorithms

### 5.1 PWD_WA hash format (ID8.A02 + ID8.A08)

```
blob = [1][key_id][12B IV][2B LE encKeyLen][RSA/PKCS1(AES_key)][16B GCM_tag][GCM_ciphertext]
PWD_WA = "#PWD_WA:11:{timestamp}:{urlsafe_base64_nopad(blob)}"
```

- AES-GCM with 12-byte nonce, 16-byte tag
- RSA/PKCS1v1.5 (NOT OAEP) for key wrapping
- URL-safe base64, no padding (Base64 flag=11)

### 5.2 Plaintext encryption (ID8.A06)

```
If RSA key >= 4096:
  AES-GCM(16-byte IV) + RSA-OAEP(SHA256), AAD=DER pubkey
Else (RSA 2048):
  AES-GCM(12-byte IV) + RSA-OAEP(SHA1), no AAD
```

### 5.3 HKDF info string

```
IJW.A00 = "Canonical Ent Companion Nonce Encrypt"
```

### 5.4 `<pem>` XML attributes

```
version="1", algorithm="rsa2048"
ttl ts_s="432000" (5 days)
key_id="1"
```

### 5.5 `<encryption-metadata>` XML attributes

```
version="1", algorithm="rsa2048"
```

### 5.6 Challenges structure

```xml
<challenges>
  <supported>
    <friction variant="1"/>
    <passkey-create/>
  </supported>
</challenges>
```

### 5.7 client-props (PairingClientProps)

```protobuf
is_chat_db_lid_migrated = true
is_syncd_pure_lid_session = true
is_syncd_snapshot_recovery_enabled = true
is_hs_thumbnail_sync_enabled = true
```

---

## 6. Real-Device Packet Reference

```xml
<iq to='s.whatsapp.net' id='05' xmlns='md' type='set'>
  <pair-device>
    <ref>2@Nulj87/NMaAkX3KxBtJeHMQVevgDo4geL1bMGImgpG7Sa5UiEON5IHbdq9PBvM5549OcsCRiyVWo1wkn8ZISM0PmY4JpYjy5qg0=</ref>
    <pub-key>vJSbaZW52Df7wXj9Hey8qDaK/Kb5yuXi7EL0DVE+gBQ=</pub-key>
    <device-identity>CngKEgjliuzMBxCXjYbTBhgCIAAoABIgoytrCYhVRQSRJJ3VAq5Amf8NScewdptPE8hvCmQgtmoaQDEbeH5qRX3sW21rogB6cxOcBFF8++QgluHj7JA83wB4HaRXKCMbIKyPpUHmxw28Or/D4N6U56TE2W6remN7HwoSIJY216cyyYR5wuPfdZ+owpIeuJjoX5yYkD0ratqnskTYGAA=</device-identity>
    <key-index-list ts='1784776343'>ChUI5YrszAcQl42G0wYYAiIDAAECKAASQP5qCOJcblCA/cSMEZj7shnGu5nw06UZcI4hA7mtJEbM8Up5f/uJ1S7nLEy3ju1xi7IQKPMCMc+fy1Nte+NYugs=</key-index-list>
    <client-props></client-props>
    <pem version='1' algorithm='rsa2048'>
      <pem>GcUZRNkj752G6lia8GlbdUhrEmTGdT1WajvNhHOGhlQ=</pem>
      <ttl ts_s='432000'/>
      <key_id>1</key_id>
    </pem>
    <encryption-metadata version='1' algorithm='rsa2048'>
      <encrypted_key>AdSzsWIVFMt31udk2KLESwmExUEsK3HgooraIHBxit2OabDFVHYKlKgBkNa+5PS1Akrrxxr0abvoHjhjD1J51JprUoC7TBcWVHzahtLBeSGLIRZhT+2LXYsjxxrmEtx6kvfb/tlP0Ju29/9Dhsd65fWiSDRhBja8WDxQWi8b0MSofetiMXGK3xqX/FBZ9x4eeCo/K2Rx0JrtuAiQFbv9uYJGla3EyMEmIqKtWwZs7T68Ze7OnTk4kGarr6mUOL1/YRCDn1EeYOCSoIUwN1s3ixpDNf6HNgAihSTLhSK2imOJ+GRlyPI/SvEfxmIixp2GNs9fEeZRtJxmoP3I/Z3nZQ==</encrypted_key>
      <nonce>ewnHAoXEjIwBoMuG</nonce>
      <encrypted_data>AyX0YIW/UfktS0fVPHoLuIDmKGFUHjFugOkyIskQ76x/...</encrypted_data>
      <auth_tag>9LSBjUT2TcwdOYRYf/asBw==</auth_tag>
    </encryption-metadata>
    <challenges>
      <supported>
        <friction variant='1'/>
        <passkey-create/>
      </supported>
    </challenges>
  </pair-device>
</iq>
```

**Note**: All base64 values in the packet log are the **display representation** of raw bytes.
The binary wire protocol sends raw bytes directly via `ProtocolTreeNode.data`.

---

## 7. Summary of Required Fixes

| Bug | File | Fix |
|-----|------|-----|
| BUG-A | `qr_crypto.py` | `derive_secret_key`: salt=None (not noise_pub) for first pairing |
| BUG-B | `iq_md_pair_device.py` | `<pem>` data: raw bytes (not base64-encoded) |
| BUG-C | `iq_md_pair_device.py` | `<encryption-metadata>` fields: raw bytes (not base64-encoded) |
| BUG-D | `md_link.py` | Use stored canonical password (not adv_secret) for PWD_WA hash |
| BUG-E | `md_link.py` | Use password_pem as client_pub_key (not new RSA key) |
| BUG-F | `md_link.py` | Use password_pem for PWD_WA RSA encryption (not new RSA key) |
| BUG-G | `md_link.py` | Use `build_pwd_wa_hash` (not `build_password_hash`) for encryption-metadata |