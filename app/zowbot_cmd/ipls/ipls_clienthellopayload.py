"""ipls.clienthellopayload command — generate client_hello_payload and send IplsClientHelloPayload mutation.

Usage:
  ipls.clienthellopayload <server_hello_payload> <session_id> [request_type] [existing_keys_b64]

Params:
  server_hello_payload : base64 string from ipls.clienthandshakeinitrequest
  session_id           : base64 string from ipls.clienthandshakeinitrequest
  request_type         : "GET" (default) or "PUT"
  existing_keys_b64    : (PUT only) base64 JSON array of existing keys from GET response
                        e.g. [{"key_id":1,"key":"base64key"},...]
"""

import base64
import hashlib
import hmac
import json
import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.zowbot_cmd.base import BotCommand
from app.param_not_enough_exception import ParamsNotEnoughException
from axolotl.ecc.curve import Curve
from axolotl.ecc.djbec import DjbECPrivateKey, DjbECPublicKey
from common.utils import Utils
from core.layers.protocol_iq.protocolentities import (
    WmexQueryIqProtocolEntity,
    WmexResultIqProtocolEntity,
)

logger = logging.getLogger(__name__)

# ── Protobuf wire-format helpers (proto3 semantics) ──────────────────────

def _encode_varint(value: int) -> bytes:
    """Encode an unsigned integer as a protobuf varint."""
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value & 0x7F)
    return bytes(out)


def _tag(field_number: int, wire_type: int) -> bytes:
    return _encode_varint((field_number << 3) | wire_type)


def _enc_bytes(field_number: int, value: bytes) -> bytes:
    """Encode a bytes/string field (wire type 2). Empty → omitted (proto3)."""
    if value is None or len(value) == 0:
        return b""
    if isinstance(value, str):
        value = value.encode("utf-8")
    return _tag(field_number, 2) + _encode_varint(len(value)) + value


def _enc_varint(field_number: int, value: int) -> bytes:
    """Encode a varint field (wire type 0). 0 → omitted (proto3)."""
    if value == 0:
        return b""
    return _tag(field_number, 0) + _encode_varint(value)


def _enc_msg(field_number: int, data: bytes) -> bytes:
    """Encode a nested message field (wire type 2). Empty → omitted."""
    if data is None or len(data) == 0:
        return b""
    return _tag(field_number, 2) + _encode_varint(len(data)) + data


def _read_varint(data: bytes, pos: int) -> tuple:
    result = 0
    shift = 0
    while True:
        b = data[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return result, pos


def _parse_fields(data: bytes) -> dict:
    """Parse raw protobuf bytes → {field_number: [value, ...]}."""
    fields: dict = {}
    pos = 0
    while pos < len(data):
        tag_val, pos = _read_varint(data, pos)
        fn = tag_val >> 3
        wt = tag_val & 0x07
        if wt == 0:  # varint
            val, pos = _read_varint(data, pos)
        elif wt == 2:  # length-delimited
            length, pos = _read_varint(data, pos)
            val = data[pos : pos + length]
            pos += length
        elif wt == 5:  # 32-bit
            val = data[pos : pos + 4]
            pos += 4
        elif wt == 1:  # 64-bit
            val = data[pos : pos + 8]
            pos += 8
        else:
            break
        fields.setdefault(fn, []).append(val)
    return fields


# ── Protobuf message builders ─────────────────────────────────────────────
#
# C44877Jwc (handshake material)
#   1: accountJid_          (string)
#   2: sessionId_           (string)
#   3: challengeResponse_   (bytes, 64B Ed25519 sig)
#   4: cikPub_              (bytes, 32B)
#   5: cekPub_              (bytes, 32B)
#   6: kemCiphertext_       (bytes, not set)
#   7: cekPubSignature_     (bytes, not set)
#   8: requestType_         (varint, 0=GET, 1=PUT)
#
# C44874JwZ (encrypted payload container)
#   1: requestType_              (varint)
#   2: handshakeMaterial_        (C44877Jwc)
#   3: iplsClientSecretData_     (C44871JwW, only for PUT)
#
# C44871JwW (client secret data)
#   1: clientSecretMap_  → map<string, C44872JwX>
#      encoded as repeated message: {1: key(string), 2: value(C44872JwX)}
#
# C44872JwX (key collection)
#   1: clientSecretKey_  → repeated C1C3
#
# C1C3 (single key entry)
#   1: keyId_                  (int64)
#   2: clientSecretKeyData_    (bytes, 32B)
#
# C44873JwY (final client_hello_payload)
#   1: clientHelloHandshakeMaterial_       (C44877Jwc)
#   2: iplsClientRequestEncryptedPayload_  (bytes, AES-GCM ciphertext)
#   3: iv_                                 (bytes, 12B)


def _build_jwc(account_jid: str, session_id: str, challenge_resp: bytes,
               cik_pub: bytes, cek_pub: bytes, request_type: int) -> bytes:
    # field 8 (requestType_) is proto3 optional — always serialize, even when 0
    # (Java code does bitField0_ |= 128 to mark it as explicitly set)
    return (
        _enc_bytes(1, account_jid.encode())
        + _enc_bytes(2, session_id.encode())
        + _enc_bytes(3, challenge_resp)
        + _enc_bytes(4, cik_pub)
        + _enc_bytes(5, cek_pub)
        + _tag(8, 0) + _encode_varint(request_type)
    )


def _build_c1c3(key_id: int, key_data: bytes) -> bytes:
    return _enc_varint(1, key_id) + _enc_bytes(2, key_data)


def _build_jwx(key_entries: list) -> bytes:
    """C44872JwX: repeated C1C3 at field 1."""
    return b"".join(_enc_msg(1, e) for e in key_entries)


def _build_jww(map_entries: dict) -> bytes:
    """C44871JwW: map<string, C44872JwX> at field 1."""
    out = b""
    for key, value in map_entries.items():
        entry = _enc_bytes(1, key.encode()) + _enc_msg(2, value)
        out += _enc_msg(1, entry)
    return out


def _build_jwz(request_type: int, jwc: bytes, jww: bytes = None) -> bytes:
    # field 1 (requestType_) is proto2 optional — always serialize, even when 0
    # (C44874JwZ has bitField0_, builder sets it via A01())
    out = _tag(1, 0) + _encode_varint(request_type) + _enc_msg(2, jwc)
    if jww:
        out += _enc_msg(3, jww)
    return out


def _build_jwy(jwc: bytes, encrypted: bytes, iv: bytes) -> bytes:
    return _enc_msg(1, jwc) + _enc_bytes(2, encrypted) + _enc_bytes(3, iv)


# ── HKDF (RFC 5869, SHA-256) ──────────────────────────────────────────────

def _hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    return hmac.new(salt, ikm, hashlib.sha256).digest()


def _hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    out = bytearray()
    t = b""
    block = 0
    while len(out) < length:
        block += 1
        mac = hmac.new(prk, t + info + bytes([block]), hashlib.sha256)
        t = mac.digest()
        out.extend(t)
    return bytes(out[:length])


def _hkdf(ikm: bytes, info: bytes, length: int, salt: bytes = None) -> bytes:
    if salt is None:
        salt = b"\x00" * 32
    prk = _hkdf_extract(salt, ikm)
    return _hkdf_expand(prk, info, length)


# ── Command ──────────────────────────────────────────────────────────────


class Cmd_Ipls_ClientHelloPayload(BotCommand):
    COMMAND = "ipls.clienthellopayload"
    DESCRIPTION = "Generate client_hello_payload and send IplsClientHelloPayload"

    # KH5 enum: A02=GET(0), A03=PUT(1)
    _KH5_GET = 0
    _KH5_PUT = 1

    async def execute(self, params, options):
        if len(params) < 2:
            raise ParamsNotEnoughException()

        server_hello_b64 = params[0]
        session_id_b64 = params[1]
        request_type_str = params[2].upper() if len(params) > 2 else "GET"
        is_put = request_type_str == "PUT"
        kh5_request = self._KH5_PUT if is_put else self._KH5_GET

        try:
            # ── Step 1: Parse server_hello_payload (C44878Jwd) ────────────
            sh_bytes = base64.b64decode(server_hello_b64)
            sh_fields = _parse_fields(sh_bytes)

            hek_pub = sh_fields[1][0]  # field 1: hekPub_ (32B)
            hk_pub = sh_fields[2][0]   # field 2: hkPub_ (32B)
            hsm_challenge = sh_fields[5][0]  # field 5: hsmChallenge_

            logger.info(
                f"server_hello parsed: hek_pub={len(hek_pub)}B "
                f"hk_pub={len(hk_pub)}B hsm_challenge={len(hsm_challenge)}B"
            )

            # ── Step 2: Get CIK from identity store ──────────────────────
            layer = self.bot.botLayer
            identity = layer.db.identity
            cik_private = identity.privateKey  # DjbECPrivateKey
            cik_pub_32b = identity.publicKey.serialize()[1:]  # strip 0x05 prefix

            # ── Step 3: Generate CEK ephemeral keypair ────────────────────
            cek_keypair = Curve.generateKeyPair()
            cek_private = cek_keypair.privateKey  # DjbECPrivateKey
            cek_pub = cek_keypair.publicKey       # DjbECPublicKey
            cek_pub_32b = cek_pub.serialize()[1:]  # strip 0x05 → 32B

            # ── Step 4: 3x ECDH (X25519) ──────────────────────────────────
            # CG6.A08(privKey, pubKey) = calculateAgreement(pubKey, privKey)
            shared_1 = Curve.calculateAgreement(
                DjbECPublicKey(hek_pub), cik_private
            )
            shared_2 = Curve.calculateAgreement(
                DjbECPublicKey(hk_pub), cek_private
            )
            shared_3 = Curve.calculateAgreement(
                DjbECPublicKey(hek_pub), cek_private
            )

            # Concatenate: C1UZ.A06(shared_1, shared_2, shared_3)
            combined = shared_1 + shared_2 + shared_3  # 96 bytes

            # ── Step 5: HKDF → derive encryption keys ─────────────────────
            # C1V0.A00(combined, info="IPLS", length=64)
            # = HKDF-Extract(salt=0x00*32, IKM=combined) → Expand(info="IPLS", L=64)
            hkdf_out = _hkdf(combined, b"IPLS", 64)

            # Split: [0:32] = client_secret_key (encrypt), [32:64] = server_secret_key (decrypt)
            client_secret_key = hkdf_out[0:32]
            server_secret_key = hkdf_out[32:64]

            logger.info(
                f"3xECDH done, derived keys: "
                f"client={client_secret_key.hex()[:16]}... "
                f"server={server_secret_key.hex()[:16]}..."
            )

            # ── Step 6: Build C44877Jwc (handshake material) ──────────────
            # challengeResponse = CG6.A09(CEK_private, hsmChallenge)
            #   = Curve.calculateSignature(cek_private, hsm_challenge)
            challenge_response = Curve.calculateSignature(
                cek_private, hsm_challenge
            )  # 64 bytes

            # accountJid must be full JID e.g. "12366198429@s.whatsapp.net"
            account_jid = layer.getProp("jid") or self.bot.botId
            if "@" not in account_jid:
                account_jid = account_jid + "@s.whatsapp.net"

            jwc = _build_jwc(
                account_jid=account_jid,
                session_id=session_id_b64,
                challenge_resp=challenge_response,
                cik_pub=cik_pub_32b,
                cek_pub=cek_pub_32b,
                request_type=kh5_request,
            )

            # ── Step 7: Build C44874JwZ (payload to encrypt) ─────────────
            jww = None
            if is_put:
                # PUT mode: upload client secret keys to server
                # Must include ALL existing keys from GET handshake + 1 new key
                # (L9n.A02 native_contacts branch)

                # Parse existing keys from optional 4th param (base64 JSON array)
                existing_keys = []
                if len(params) > 3:
                    try:
                        existing_keys = json.loads(
                            base64.b64decode(params[3]).decode()
                        )
                    except Exception:
                        existing_keys = []

                # Generate new key
                random_key = os.urandom(32)
                derived_key = _hkdf(random_key, b"IPLS", 32)

                # keyId = max(existing keyIds) + 1, or 1 if no existing keys
                max_key_id = 0
                for ek in existing_keys:
                    if ek.get("key_id", 0) > max_key_id:
                        max_key_id = ek["key_id"]
                new_key_id = max_key_id + 1

                # Build C1C3 entries: new key first, then all existing keys
                c1c3_entries = [_build_c1c3(new_key_id, derived_key)]
                for ek in existing_keys:
                    ek_id = ek.get("key_id", 0)
                    ek_data = base64.b64decode(ek.get("key", ""))
                    if ek_data and ek_id > 0:
                        c1c3_entries.append(_build_c1c3(ek_id, ek_data))

                # Truncate to 50 keys max (C49178LrV.A00 + AbstractC02330Bg.A1J)
                c1c3_entries = c1c3_entries[:50]

                jwx = _build_jwx(c1c3_entries)
                jww = _build_jww({"native_contacts": jwx})

                logger.info(
                    f"PUT mode: {len(c1c3_entries)} keys "
                    f"(1 new + {len(existing_keys)} existing), "
                    f"new keyId={new_key_id}"
                )

            jwz = _build_jwz(kh5_request, jwc, jww)

            # ── Step 8: AES-256-GCM encrypt ───────────────────────────────
            iv = os.urandom(12)
            aesgcm = AESGCM(client_secret_key)
            encrypted = aesgcm.encrypt(iv, jwz, None)
            # Python cryptography: encrypted = ciphertext + 16B GCM tag

            # ── Step 9: Assemble C44873JwY (client_hello_payload) ─────────
            jwy = _build_jwy(jwc, encrypted, iv)
            client_hello_payload = base64.b64encode(jwy).decode()

            logger.info(
                f"client_hello_payload generated: {len(jwy)}B raw, "
                f"{len(client_hello_payload)}B b64"
            )

            # ── Step 10: Send IplsClientHelloPayload mutation ─────────────
            # Real device capture shows type='get' (not 'set')
            query = {
                "variables": {
                    "input": {
                        "client_hello_payload": client_hello_payload,
                    }
                }
            }

            entity = WmexQueryIqProtocolEntity(
                query_name="IplsClientHelloPayload", query_obj=query
            )
            result = await self.send_iq_expect(entity, WmexResultIqProtocolEntity)

            logger.info(f"IplsClientHelloPayload response: {result.result_obj}")

            # ── Step 11: Decrypt server_finish_payload ────────────────────
            # server_finish_payload is base64(C44875Jwa protobuf):
            #   field 1: iplsClientSecretDataEncrypted_ (bytes, encrypted C44871JwW)
            #   field 2: serverHelloHandshakeMaterial or similar (bytes)
            #   field 3: iv_ (bytes, 12B)
            #
            # L9n.A03: decrypt field 1 with server_secret_key + iv using AES-GCM
            server_finish_b64 = (
                result.result_obj.get("data", {})
                .get("xwa2_ipls_client_hello", {})
                .get("server_finish_payload")
            )

            decrypted_secret_data = None
            secret_keys = []
            if server_finish_b64:
                # server_finish_payload is base64(C44875Jwa protobuf):
                #   field 1: iplsClientSecretDataEncrypted_ (base64 string)
                #   field 2: encrypted C44871JwW (the actual ciphertext, if present)
                #   field 3: iv_ (12B, if present)
                #
                # GET mode: server returns encrypted secret keys
                # PUT mode: server may just echo session_id (no encrypted data)
                #
                # L9n.A03: decrypt field 2 with server_secret_key + iv using AES-GCM
                try:
                    sf_bytes = base64.b64decode(server_finish_b64)
                    sf_fields = _parse_fields(sf_bytes)

                    # Only decrypt if field 2 (ciphertext) and field 3 (iv) exist
                    if 2 in sf_fields and 3 in sf_fields:
                        sf_encrypted = sf_fields[2][0]  # field 2: encrypted data
                        sf_iv = sf_fields[3][0]          # field 3: iv (12B)

                        # AES-GCM decrypt with server_secret_key
                        sf_aesgcm = AESGCM(server_secret_key)
                        decrypted_secret_data = sf_aesgcm.decrypt(sf_iv, sf_encrypted, None)

                        # Parse C44871JwW → map<string, C44872JwX>
                        # C44871JwW field 1 = map entry: {1: key(string), 2: C44872JwX}
                        # C44872JwX field 1 = repeated C1C3: {1: keyId(int64), 2: key(bytes 32B)}
                        jww_fields = _parse_fields(decrypted_secret_data)
                        for map_entry_raw in jww_fields.get(1, []):
                            entry_fields = _parse_fields(map_entry_raw)
                            map_key = entry_fields.get(1, [b""])[0]
                            if isinstance(map_key, bytes):
                                map_key = map_key.decode("utf-8", errors="replace")
                            jwx_raw = entry_fields.get(2, [b""])[0]
                            jwx_fields = _parse_fields(jwx_raw)
                            for c1c3_raw in jwx_fields.get(1, []):
                                c1c3_fields = _parse_fields(c1c3_raw)
                                key_id = c1c3_fields.get(1, [0])[0]
                                key_data = c1c3_fields.get(2, [b""])[0]
                                secret_keys.append({
                                    "map_key": map_key,
                                    "key_id": key_id,
                                    "key": base64.b64encode(key_data).decode(),
                                })

                        logger.info(
                            f"server_finish decrypted: {len(decrypted_secret_data)}B, "
                            f"{len(secret_keys)} secret keys"
                        )
                    else:
                        logger.info(
                            "server_finish has no encrypted data "
                            "(PUT mode echo only)"
                        )
                except Exception as de:
                    logger.warning(f"Failed to decrypt server_finish: {de}")

            return self.success(
                client_hello_payload=client_hello_payload,
                server_secret_key=base64.b64encode(server_secret_key).decode(),
                client_secret_key=base64.b64encode(client_secret_key).decode(),
                server_finish_payload=server_finish_b64,
                server_secret_keys=secret_keys,
                response=result.result_obj,
            )

        except Exception as e:
            logger.error(f"clienthellopayload error: {e}", exc_info=True)
            return self.fail(error=str(e))