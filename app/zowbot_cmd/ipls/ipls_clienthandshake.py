"""ipls.clienthandshake command — complete IPLS handshake (GET + PUT) in one step.

Usage:
  ipls.clienthandshake

No params needed — automatically does the full flow:
  1. IplsClientHandshakeInitRequest GET  → server_hello
  2. IplsClientHelloPayload GET          → get server secret keys
  3. IplsClientHandshakeInitRequest PUT  → new server_hello
  4. IplsClientHelloPayload PUT          → upload client keys (server keys + new key)
"""

import base64
import hashlib
import hmac
import json
import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.zowbot_cmd.base import BotCommand
from axolotl.ecc.curve import Curve
from axolotl.ecc.djbec import DjbECPrivateKey, DjbECPublicKey
from core.layers.protocol_iq.protocolentities import (
    WmexQueryIqProtocolEntity,
    WmexResultIqProtocolEntity,
)

from app.zowbot_cmd.ipls.ipls_clienthellopayload import (
    _parse_fields,
    _build_jwc,
    _build_c1c3,
    _build_jwx,
    _build_jww,
    _build_jwz,
    _build_jwy,
    _hkdf,
)

logger = logging.getLogger(__name__)

_KH5_GET = 0
_KH5_PUT = 1


class Cmd_Ipls_ClientHandshake(BotCommand):
    COMMAND = "ipls.clienthandshake"
    DESCRIPTION = "Complete IPLS handshake (GET + PUT) in one step"

    async def execute(self, params, options):
        try:
            # ══════════════════════════════════════════════════════════════
            # Phase 1: GET handshake — get server secret keys
            # ══════════════════════════════════════════════════════════════
            logger.info("=== Phase 1: GET handshake ===")

            # 1a. IplsClientHandshakeInitRequest GET
            session_id_get = os.urandom(32)
            session_id_get_b64 = base64.b64encode(session_id_get).decode()

            init_entity = WmexQueryIqProtocolEntity(
                query_name="IplsClientHandshakeInitRequest",
                query_obj={
                    "variables": {
                        "request_type": "GET",
                        "session_id": session_id_get_b64,
                    }
                },
            )
            init_result = await self.send_iq_expect(
                init_entity, WmexResultIqProtocolEntity
            )

            server_hello_get = (
                init_result.result_obj["data"]["xwa2_ipls_client_init"]
                ["server_hello_payload"]
            )
            logger.info(f"GET init: server_hello received")

            # 1b. IplsClientHelloPayload GET
            get_keys, get_client_key, get_server_key = await self._do_hello(
                server_hello_get, session_id_get_b64, _KH5_GET, None
            )
            logger.info(f"GET hello: {len(get_keys)} server keys received")

            # ══════════════════════════════════════════════════════════════
            # Phase 2: PUT handshake — upload client + server keys
            # ══════════════════════════════════════════════════════════════
            logger.info("=== Phase 2: PUT handshake ===")

            # 2a. IplsClientHandshakeInitRequest PUT
            session_id_put = os.urandom(32)
            session_id_put_b64 = base64.b64encode(session_id_put).decode()

            init_entity2 = WmexQueryIqProtocolEntity(
                query_name="IplsClientHandshakeInitRequest",
                query_obj={
                    "variables": {
                        "request_type": "PUT",
                        "session_id": session_id_put_b64,
                    }
                },
            )
            init_result2 = await self.send_iq_expect(
                init_entity2, WmexResultIqProtocolEntity
            )

            server_hello_put = (
                init_result2.result_obj["data"]["xwa2_ipls_client_init"]
                ["server_hello_payload"]
            )
            logger.info(f"PUT init: server_hello received")

            # 2b. IplsClientHelloPayload PUT (with existing keys from GET)
            put_keys, put_client_key, put_server_key = await self._do_hello(
                server_hello_put, session_id_put_b64, _KH5_PUT, get_keys
            )
            logger.info(f"PUT hello: complete")

            return self.success(
                get_server_keys=get_keys,
                get_client_secret_key=get_client_key,
                get_server_secret_key=get_server_key,
                put_server_keys=put_keys,
                put_client_secret_key=put_client_key,
                put_server_secret_key=put_server_key,
            )

        except Exception as e:
            logger.error(f"clienthandshake error: {e}", exc_info=True)
            return self.fail(error=str(e))

    async def _do_hello(
        self,
        server_hello_b64: str,
        session_id_b64: str,
        kh5_request: int,
        existing_keys: list = None,
    ) -> tuple:
        """Do one hello handshake step. Returns (secret_keys, client_key_b64, server_key_b64)."""

        # Parse server_hello_payload
        sh_bytes = base64.b64decode(server_hello_b64)
        sh_fields = _parse_fields(sh_bytes)
        hek_pub = sh_fields[1][0]
        hk_pub = sh_fields[2][0]
        hsm_challenge = sh_fields[5][0]

        # Get CIK from identity store
        layer = self.bot.botLayer
        identity = layer.db.identity
        cik_private = identity.privateKey
        cik_pub_32b = identity.publicKey.serialize()[1:]

        # Generate CEK ephemeral keypair
        cek_keypair = Curve.generateKeyPair()
        cek_private = cek_keypair.privateKey
        cek_pub_32b = cek_keypair.publicKey.serialize()[1:]

        # 3x ECDH
        shared_1 = Curve.calculateAgreement(DjbECPublicKey(hek_pub), cik_private)
        shared_2 = Curve.calculateAgreement(DjbECPublicKey(hk_pub), cek_private)
        shared_3 = Curve.calculateAgreement(DjbECPublicKey(hek_pub), cek_private)
        combined = shared_1 + shared_2 + shared_3

        # HKDF → derive keys
        hkdf_out = _hkdf(combined, b"IPLS", 64)
        client_secret_key = hkdf_out[0:32]
        server_secret_key = hkdf_out[32:64]

        # Build C44877Jwc
        challenge_response = Curve.calculateSignature(cek_private, hsm_challenge)

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

        # Build C44874JwZ
        jww = None
        is_put = kh5_request == _KH5_PUT
        if is_put:
            # Include existing keys from GET + 1 new key
            random_key = os.urandom(32)
            derived_key = _hkdf(random_key, b"IPLS", 32)

            max_key_id = 0
            for ek in (existing_keys or []):
                if ek.get("key_id", 0) > max_key_id:
                    max_key_id = ek["key_id"]
            new_key_id = max_key_id + 1

            c1c3_entries = [_build_c1c3(new_key_id, derived_key)]
            for ek in (existing_keys or []):
                ek_id = ek.get("key_id", 0)
                ek_data = base64.b64decode(ek.get("key", ""))
                if ek_data and ek_id > 0:
                    c1c3_entries.append(_build_c1c3(ek_id, ek_data))

            c1c3_entries = c1c3_entries[:50]
            jwx = _build_jwx(c1c3_entries)
            jww = _build_jww({"native_contacts": jwx})

            # Log uploaded keys for comparison with GET
            for ek in (existing_keys or []):
                logger.info(
                    f"PUT uploading existing key_id={ek.get('key_id')} "
                    f"key={ek.get('key')}"
                )
            logger.info(
                f"PUT uploading NEW key_id={new_key_id} "
                f"key={base64.b64encode(derived_key).decode()}"
            )

            logger.info(
                f"PUT: {len(c1c3_entries)} keys "
                f"(1 new + {len(existing_keys or [])} existing)"
            )

        jwz = _build_jwz(kh5_request, jwc, jww)

        # AES-GCM encrypt
        iv = os.urandom(12)
        aesgcm = AESGCM(client_secret_key)
        encrypted = aesgcm.encrypt(iv, jwz, None)

        # Assemble C44873JwY
        jwy = _build_jwy(jwc, encrypted, iv)
        client_hello_payload = base64.b64encode(jwy).decode()

        # Send IplsClientHelloPayload
        entity = WmexQueryIqProtocolEntity(
            query_name="IplsClientHelloPayload",
            query_obj={
                "variables": {
                    "input": {
                        "client_hello_payload": client_hello_payload,
                    }
                }
            },
        )
        result = await self.send_iq_expect(entity, WmexResultIqProtocolEntity)

        # Decrypt server_finish_payload (GET mode only)
        secret_keys = []
        server_finish_b64 = (
            result.result_obj.get("data", {})
            .get("xwa2_ipls_client_hello", {})
            .get("server_finish_payload")
        )

        if server_finish_b64:
            try:
                sf_bytes = base64.b64decode(server_finish_b64)
                sf_fields = _parse_fields(sf_bytes)

                if 2 in sf_fields and 3 in sf_fields:
                    sf_encrypted = sf_fields[2][0]
                    sf_iv = sf_fields[3][0]

                    sf_aesgcm = AESGCM(server_secret_key)
                    decrypted = sf_aesgcm.decrypt(sf_iv, sf_encrypted, None)

                    jww_fields = _parse_fields(decrypted)
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
                        f"server_finish decrypted: {len(decrypted)}B, "
                        f"{len(secret_keys)} keys"
                    )
                else:
                    logger.info("server_finish: no encrypted data (PUT echo)")
            except Exception as de:
                logger.warning(f"Failed to decrypt server_finish: {de}")

        return (
            secret_keys,
            base64.b64encode(client_secret_key).decode(),
            base64.b64encode(server_secret_key).decode(),
        )