
import base64
import logging
import uuid
from datetime import datetime

from Crypto.Cipher import AES, PKCS1_v1_5, PKCS1_OAEP
from Crypto.Hash import SHA1, SHA256
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
from core.layers.protocol_iq.protocolentities import WmexQueryIqProtocolEntity

logger = logging.getLogger(__name__)

#  Module-level storage: set by protocol_ib layer when recovery_nonce arrives.
#  Consumed by www.triggeracountrecovery command.
_pending_nonce: str | None = None

#  Default use_case for the canonical credential flow.
#  CANONICAL (fbid=1047219231815734) and DIGITAL_COMMERCE (fbid=1151993101338866)
#  use different fb_ids AND different certificate chains with different key_ids.
#  All three requests (GetCertificates, Trigger, Exchange) must use the SAME use_case.
DEFAULT_USE_CASE = "CANONICAL"


PASSWORD_CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+{}"


def _b64_dfl(data: bytes) -> str:
    """Base64 flag=0 — LF every 76 chars, trailing LF (matches wire capture)."""
    e = base64.b64encode(data).decode()
    return "\n".join(e[i:i+76] for i in range(0, len(e), 76)) + "\n"


def _b64_urlsafe_nopad(data: bytes) -> str:
    """Base64 flag=11 (URL_SAFE|NO_WRAP|NO_PADDING)."""
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _rand_pwd() -> str:
    """JJ5.A00() → random 50-char password (confirmed from APK source)."""
    import secrets
    return "".join(secrets.choice(PASSWORD_CHARSET) for _ in range(50))


def _jj5_a01(public_key) -> str:

    der = public_key.export_key(format="DER")
    b64 = base64.b64encode(der).decode()
    return f"-----BEGIN PUBLIC KEY-----\n{b64}\n-----END PUBLIC KEY-----\n"


def build_pwd_wa_hash(password: str, key_id: int, pubkey_pem: str, timestamp: int) -> str:

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
    blob.extend(elen.to_bytes(2, "little"))  # matches APK ByteBuffer(ByteOrder.LITTLE_ENDIAN)
    blob.extend(enc_key)
    blob.extend(tag)
    blob.extend(ctxt)

    return f"#PWD_WA:11:{timestamp}:{_b64_urlsafe_nopad(bytes(blob))}"


def encrypt_with_cert(plaintext: str, cert_pem: str):
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    cert = x509.load_pem_x509_certificate(cert_pem.strip().encode(), default_backend())
    der = cert.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    rsa_pub = RSA.import_key(der)
    key_sz = rsa_pub.size_in_bits()
    aes_key = get_random_bytes(32)

    if key_sz >= 4096:
        iv = get_random_bytes(16)
        cipher = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
        cipher.update(der)
        ctxt, tag = cipher.encrypt_and_digest(plaintext.encode("utf-8"))
        enc_key = PKCS1_OAEP.new(rsa_pub, hashAlgo=SHA256).encrypt(aes_key)
    else:
        iv = get_random_bytes(12)
        cipher = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
        ctxt, tag = cipher.encrypt_and_digest(plaintext.encode("utf-8"))
        enc_key = PKCS1_OAEP.new(rsa_pub, hashAlgo=SHA1).encrypt(aes_key)

    return enc_key, ctxt, tag, iv

def decrypt_response(enc_key: bytes, ctxt: bytes, tag: bytes, nonce: bytes, privkey: RSA.RsaKey) -> str:
    aes_key = PKCS1_OAEP.new(privkey, hashAlgo=SHA1).decrypt(enc_key)
    cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ctxt, tag).decode("utf-8")


async def trigger_account_recovery(layer, trace_id: str | None = None,
                                   use_case: str | None = None) -> dict | None:
    """Send WWWTriggerAcountRecovery. Returns {fb_id, registration_trace_id}.

    Real device order: GetCertificates FIRST, then Trigger.

    Args:
        layer: The protocol layer.
        trace_id: Optional registration trace ID (auto-generated if None).
        use_case: "CANONICAL" or "DIGITAL_COMMERCE". Defaults to DEFAULT_USE_CASE.
                  Must be consistent across GetCertificates / Trigger / Exchange.
    """
    uc = use_case or DEFAULT_USE_CASE
    layer._recovery_use_case = uc  # store for exchange_nonce_for_token

    rsa_key = RSA.generate(2048)
    pem = _jj5_a01(rsa_key.publickey())  # PEM string
    nonce_key = _b64_dfl(pem.encode("utf-8"))  # base64(PEM) matches APK: base64(utf8(JJ5.A01(pub)))

    layer._recovery_keypair = rsa_key
    reg_trace = trace_id or str(uuid.uuid4())
    layer._recovery_trace_id = reg_trace

    # Step 0: WWWGetCertificates FIRST (matches real device packet order)
    cert_query = {"variables": {"input": {
        "registration_trace_id": reg_trace,
        "request_id": str(uuid.uuid4()),
        "request_time": str(int(datetime.now().timestamp())),
        "use_case": uc,
    }}}
    
    try:
        cert_entity = WmexQueryIqProtocolEntity(query_name="WWWGetCertificates", query_obj=cert_query)
        cert_result = (await layer._sendIqAsync(cert_entity)).get("result")
        if cert_result:
            cert_json = getattr(cert_result, "result_obj", None) or {}
            if isinstance(cert_json, dict):
                d = cert_json.get("data", {})
                if isinstance(d, dict):
                    certs = d.get("xwa2_ent_get_certificates", {})
                    layer._www_encryption_pem = certs.get("encryption_pem").get("pem","")
                    layer._www_signature_pem = certs.get("signature_pem").get("pem","")
                    layer._www_password_pem = certs.get("password_pem").get("pem","")

    except Exception as e:
        logger.error(f"trigger: GetCertificates failed: {e}")

    # Step 0.5: fbgraphfetchpem — fetch CANONICAL password_pem with correct key_id
    # GetCertificates (w:mex) returns generic certs; fbgraphfetchpem (fb:graphql)
    # returns use_case-specific password_pem with explicit key_id attribute.
    try:
        from core.layers.protocol_iq.protocolentities.fb.fb_graphql_fetch_pem import (
            FbGraphqlFetchPem,
            ResultFbGraphqlFetchPemIqProtocolEntity,
        )
        fb_entity = FbGraphqlFetchPem(use_case=uc)
        fb_result = await layer._sendIqAsync(fb_entity)
        if fb_result:
            fb_pem = fb_result.get("result")
            if fb_pem and isinstance(fb_pem, ResultFbGraphqlFetchPemIqProtocolEntity):
                if fb_pem.password_pem:
                    layer._fb_password_pem = fb_pem.password_pem
                if fb_pem.password_pem_key_id:
                    layer._fb_password_pem_key_id = int(fb_pem.password_pem_key_id)
    except Exception as e:
        logger.warning(f"trigger: fbgraphfetchpem failed (non-fatal): {e}")

    # Step 1: WWWTriggerAcountRecovery
    query = {"variables": {"input": {
        "nonce_encryption_key": nonce_key,
        "registration_trace_id": reg_trace,
        "request_id": str(uuid.uuid4()),
        "use_case": uc,
    }}}


    try:
        entity = WmexQueryIqProtocolEntity(query_name="WWWTriggerAcountRecovery", query_obj=query)
        result_entity = (await layer._sendIqAsync(entity)).get("result")
        if not result_entity:
            return None

        rj = getattr(result_entity, "result_obj", None) or {}
        d = rj.get("data", {}) if isinstance(rj, dict) else {}
        rec = d.get("xwa2_ent_request_recovery_nonce", {}) if isinstance(d, dict) else {}
        fbid = str(rec.get("fbid", "")) if isinstance(rec, dict) else ""

        if fbid:
            return {"fb_id": fbid, "registration_trace_id": reg_trace}

        logger.error(f"fbid not found: {str(rj)[:200]}")
        return None
    except Exception as e:
        logger.error(f"trigger_account_recovery failed: {e}")
        return None


async def exchange_nonce_for_token(layer, nonce_code: str) -> dict | None:
    """Exchange recovery nonce for access token.

    Uses cert data cached from trigger_account_recovery (GetCertificates already called).
    """
    nonce = nonce_code

    # Cert data: encryption_pem ALWAYS from GetCertificates (w:mex).
    # password_pem / key_id can be overridden by fbgraphfetchpem if available.
    reg_trace = getattr(layer, "_recovery_trace_id", str(uuid.uuid4()))
    encryption_pem = getattr(layer, "_www_encryption_pem", None)
    password_pem = getattr(layer, "_fb_password_pem", None) 
    password_pem_key_id = getattr(layer, "_fb_password_pem_key_id", None) 
    use_case = getattr(layer, "_recovery_use_case", DEFAULT_USE_CASE)

    if not encryption_pem or not password_pem:
        logger.error("exchange_nonce: cert data not cached (GetCertificates must be called first)")
        return None

    # Step 5-6: Generate password → PWD_WA hash → plaintext JSON → encrypt
    raw_pwd = _rand_pwd()
    ts = int(datetime.now().timestamp())

    # APK uses the SAME KeyPair from trigger for client_pub_key
    # (NOT a new one). Server validates it matches nonce_encryption_key.
    recovery_kp = getattr(layer, "_recovery_keypair", None)
    if not recovery_kp:
        logger.error("exchange_nonce: no _recovery_keypair on layer")
        return None
    client_pub = _jj5_a01(recovery_kp.publickey())

    pwd_hash = build_pwd_wa_hash(raw_pwd, key_id=password_pem_key_id, pubkey_pem=password_pem, timestamp=ts)

    import json
    plaintext = json.dumps({
        "version": 1,
        "timestamp": ts,
        "password": pwd_hash,
        "client_pub_key": client_pub,
        "client_pub_key_type": "RSA 2048",
    }, separators=(",", ":"))

    enc_key, ctxt, tag, iv = encrypt_with_cert(plaintext, encryption_pem)

    # Step 7: WWWExchangeNonceForAccessToken
    query = {"queryId": "25727187160203620","variables": {"input": {
        "encrypted_password": {
            "algorithm": "rsa2048",
            "data": _b64_dfl(ctxt),
            "key": _b64_dfl(enc_key),
            "nonce": _b64_dfl(iv),
            "tag": _b64_dfl(tag),
        },
        "nonce": nonce,
        "registration_trace_id": reg_trace,
        "request_id": str(uuid.uuid4()),
        "use_case": use_case,
    }}}

    try:
        ex_entity = WmexQueryIqProtocolEntity(query_name="WWWExchangeNonceForAccessToken", query_obj=query)
        ex_result = (await layer._sendIqAsync(ex_entity)).get("result")
        if not ex_result:
            return None

        rj = getattr(ex_result, "result_obj", None) or {}
        if isinstance(rj, dict):
            d = rj.get("data", {})
            if isinstance(d, dict):
                rec = d.get("xwa2_ent_exchange_nonce_and_password", {})
                if isinstance(rec, dict):
                    enc = rec.get("encrypted_fbid_and_access_token", {})
                    # Handle case where Argo decodes union type as list
                    if isinstance(enc, list) and len(enc) > 0:
                        enc = enc[0]
                    if isinstance(enc, dict) and enc.get("key"):
                        dk = base64.b64decode(enc.get("key", ""))
                        dd = base64.b64decode(enc.get("data", ""))
                        dt = base64.b64decode(enc.get("tag", ""))
                        dn = base64.b64decode(enc.get("nonce", ""))
                        
                        try:
                            dec = decrypt_response(dk, dd, dt, dn, recovery_kp)
                            outer = json.loads(dec)
                            # outer has {"data": "json-string", "signature": "..."}
                            # "data" is a JSON-STRING, not a dict
                            inner_str = outer.get("data", "")
                            inner = json.loads(inner_str) 
                            fbid = str(inner.get("fbid")) or ""
                            at = inner.get("access_token") or ""
                            timestamp = inner.get("timestamp") or None
                            if fbid:
                                return {"fb_id": fbid, "access_token": at, "timestamp": timestamp,"fb_password":raw_pwd}
                            else:
                                logger.error(f"exchange_nonce: fbid empty in inner data: {inner}")
                        except Exception as e:
                            logger.error(f"exchange_nonce: decrypt response failed: {e}")
                            return None

        logger.error(f"exchange_nonce: unexpected response: {str(rj)[:200]}")
        return None
    except Exception as e:
        logger.error(f"exchange_nonce: WWWExchangeNonceForAccessToken failed: {e}")
        return None







