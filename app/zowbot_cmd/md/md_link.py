from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import asyncio
import logging, base64
import uuid
import time
import json as _json
from proto import wa_struct_pb2

from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import (
    MultiDevicePairDeviceIqProtocolEntity,
    MultiDevicePairDeviceResultIqProtocolEntity,
    WmexQueryIqProtocolEntity,
    WmexResultIqProtocolEntity,
)
from core.layers.protocol_iq.protocolentities.md.iq_md_pair_device import (
    ProtocolTreeNode,
)
from common.utils import Utils
from app.layer.canonical_credentials import (
    trigger_account_recovery, exchange_nonce_for_token,
)
import app.layer.canonical_credentials as cc_module
import asyncio

from app.layer.qr_crypto import derive_secret_key


logger = logging.getLogger(__name__)


class Cmd_Md_Link(BotCommand):
    COMMAND = "md.link"
    DESCRIPTION = "Multi-device link"

    async def execute(self, params, options):
        bot = self.bot

        await bot.botLayer.resetSync(params, options)
        profile = bot.botLayer.getStack().getProp("profile")
        qr_str = params[0]

        if qr_str.startswith("https://") or qr_str.startswith("http://"):
            qr_str = qr_str.split("#")[1]
        
        qr_parts = qr_str.split(",")
        ref = qr_parts[0].encode()
        companion_noise_pub = base64.b64decode(qr_parts[1])
        companion_identity_pub = base64.b64decode(qr_parts[2])
        adv_secret = base64.b64decode(qr_parts[3])        
        
        params_v2 = Utils.generateMultiDeviceParams(
            ref=ref,
            companion_noise_pub=companion_noise_pub,
            companion_identity_pub=companion_identity_pub,
            adv_secret=adv_secret,
            account_type=0,  
            profile=profile,
        )

        layer = bot.botLayer
        encryption_pem = getattr(layer, '_www_encryption_pem', None)
        password_pem = getattr(layer, '_fb_password_pem', None)
        recovery_keypair = getattr(layer, '_recovery_keypair', None)
        fbid = getattr(layer.pairing, 'wa_fbid', None) or getattr(layer, '_fbid', None) or ""        


        need_full_flow = (not encryption_pem or
                          not password_pem or
                          not recovery_keypair)

        if need_full_flow:
            logger.info("md.link: need full canonical flow "                        
                        f"certs={'no' if not encryption_pem else 'yes'})")

            # Step 1: trigger_account_recovery (gets certs + fbid + recovery_keypair)
            creds = None
            try:
                creds = await trigger_account_recovery(layer)
                if creds:
                    logger.info(f"md.link: trigger_account_recovery ok, fb_id={creds['fb_id']}")
                else:
                    logger.warning("md.link: trigger_account_recovery returned None")
            except Exception as e:
                logger.warning(f"md.link: trigger_account_recovery failed ({e})")
            
            encryption_pem = getattr(layer, '_www_encryption_pem', None)
            # password_pem + key_id come from FbGraphqlFetchPem (fb:graphql),
            # NOT from WWWGetCertificates (w:mex). APK C33089Ejm uses FbGraphqlFetchPem result.
            password_pem = getattr(layer, '_fb_password_pem', None) or getattr(layer, '_www_password_pem', None)
            recovery_keypair = getattr(layer, '_recovery_keypair', None)
            fbid = (creds.get("fb_id") if creds else None) 
            
            layer.pairing.wa_fbid = fbid
            layer._fbid = fbid

            # Step 2+3: Wait for recovery nonce, then exchange for access_token            
            if encryption_pem and password_pem and recovery_keypair:
                logger.info("md.link: waiting for recovery nonce to exchange for WaFbPassword")
                try:
                    nonce = None
                    for _ in range(30):  # 15 second timeout
                        if cc_module._pending_nonce:
                            nonce = cc_module._pending_nonce
                            cc_module._pending_nonce = None
                            break
                        await asyncio.sleep(0.5)

                    if nonce:
                        logger.info("md.link: got recovery nonce, exchanging for access token")
                        token_result = await exchange_nonce_for_token(layer, nonce)
                        if token_result:
                            logger.info(f"md.link: exchange ok, fb_id={token_result.get('fb_id')}")     
                            layer.fb_password = token_result["fb_password"]                            
                        else:
                            logger.warning("md.link: exchange_nonce_for_token returned None")
                    else:
                        logger.warning("md.link: recovery nonce not received (timeout), "
                                       "WaFbPassword unavailable")
                except Exception as e:
                    logger.warning(f"md.link: exchange flow failed ({e})")
        else:
            logger.info("md.link: canonical creds + WaFbPassword already cached")

        # password_pem_key_id from FbGraphqlFetchPem (APK C33089Ejm.A00)
        password_pem_key_id = getattr(layer, '_fb_password_pem_key_id', None) or 1
        fb_password = getattr(layer, 'fb_password', None)

        logger.info(f"md.link certs: encryption_pem={'yes' if encryption_pem else 'no'}, "
                    f"password_pem={'yes' if password_pem else 'no'}, "
                    f"key_id={password_pem_key_id}, fbid={fbid or 'EMPTY'}, "
                    f"recovery_kp={'yes' if recovery_keypair else 'no'}")


        secret_key_bytes = None
        enc_metadata = None
        challenges_nodes = []
        client_props_bytes = None
        cert_key_id = password_pem_key_id  

        if encryption_pem is not None:

            # ── <pem> secretKey derivation ──────────────────────
            # APK IO1.A01: secretKey = HKDF(ikm=adv_secret, salt=priorAttemptKey, info=IJW.A00, 32)
            # For first pairing: priorAttemptKey = null → zero-byte salt
            secret_key_bytes = derive_secret_key(adv_secret, salt=None)

            # ── <encryption-metadata> (AuthProofHelper.A01) ──────
            # Uses STORED canonical password (WaFbPassword) — NOT adv_secret.
            # client_pub_key = password_pem (from canonical certificate).
            # PWD_WA hash uses password_pem for RSA/PKCS1 encryption.
            if fb_password and password_pem:
                from app.layer.canonical_credentials import (
                    build_pwd_wa_hash, encrypt_with_cert,
                )
                import time as _time
                enc_ts = int(_time.time())

                pwd_hash = build_pwd_wa_hash(
                    password=fb_password,
                    key_id=password_pem_key_id,
                    pubkey_pem=password_pem,
                    timestamp=enc_ts,
                )

                # APK: version = C1oQ.A18() = WhatsApp version string (e.g. "2.26.26.73")
                # We don't have the exact version string; use "1" as fallback.
                # TODO: replace with actual WA version string if server rejects.
                plaintext_json = _json.dumps({
                    "version": 1,
                    "timestamp": enc_ts,
                    "password": pwd_hash,
                    "client_pub_key": password_pem,
                    "client_pub_key_type": "RSA 2048",
                }, separators=(",", ":"))

                enc_key, enc_data, enc_tag, enc_iv = encrypt_with_cert(
                    plaintext_json, encryption_pem
                )
                enc_metadata = {
                    "encrypted_key": enc_key,
                    "nonce": enc_iv,
                    "encrypted_data": enc_data,
                    "auth_tag": enc_tag,
                }
                logger.info(f"md.link: encryption-metadata built "
                            f"(plaintext={len(plaintext_json)}B, "
                            f"ctxt={len(enc_data)}B)")
            else:
                logger.warning("md.link: cannot build encryption-metadata — "
                               f"fb_password={bool(fb_password)}, "
                               f"password_pem={bool(password_pem)}. "
                               "Server will not forward encryption-metadata to companion.")

            # Build client-props (GTH)
            client_props = wa_struct_pb2.PairingClientProps()
            client_props.is_chat_db_lid_migrated=True
            client_props.is_syncd_pure_lid_session=True
            client_props.is_syncd_snapshot_recovery_enabled=True
            client_props.is_hs_thumbnail_sync_enabled=True
            client_props_bytes = client_props.SerializeToString()

            # Challenges: real device sends friction variant=1 + passkey-create
            challenges_nodes.append(
                ProtocolTreeNode("supported", {}, [
                    ProtocolTreeNode("friction", {"variant": "1"}, None, None),
                    ProtocolTreeNode("passkey-create",{},None,None)
                ])
            )

        # ── Send pair-device IQ ────────────────────────────────
        try:
            entity = MultiDevicePairDeviceIqProtocolEntity(
                ref=params_v2["ref"],
                pubKey=params_v2["noise_pub"],
                deviceIdentity=params_v2["device_identity"],
                keyIndexList=params_v2["key_index_list"],
                keyIndexTs=params_v2["key_index_ts"],
                clientProps=client_props_bytes,
                secretKey=secret_key_bytes,
                encryptionMetadata=enc_metadata,
                challenges=challenges_nodes,
                companionQrOriginSource=None,
                certKeyId=cert_key_id,
            )

            result = await self.send_iq_expect(
                entity, MultiDevicePairDeviceResultIqProtocolEntity
            )
            companionJid = result.deviceJid
            deviceIdx = int(companionJid.split("@")[0].split(":")[1])
            profile.config.add_device_to_list(deviceIdx)
            profile.write_config(profile.config)

            bot.botLayer.getStack().setProp("pair-companion-jid", companionJid)
            logger.info(f"Device paired: {companionJid}")

            # ── Step 2: WWWGetNonceForCompanionDevice ──────────
            # Uses the SAME canonical encryption as WWWExchangeNonceForAccessToken:
            #   - PWD_WA hash with password_pem + key_id (from FbGraphqlFetchPem)
            #   - plaintext {version:1, timestamp, password, client_pub_key, client_pub_key_type}
            #   - encrypt_with_cert(encryption_pem) for encrypted_password
            #   - nonce_encryption_key = double-base64(PEM of recovery keypair pub key)
            #   - Response encrypted_nonce → RSA-OAEP decrypt with recovery keypair
            companion_nonce = await self._send_nonce_for_companion(
                device_id=deviceIdx,
                fbid=fbid,
                encryption_pem=encryption_pem,
                password_pem=password_pem,
                password_pem_key_id=password_pem_key_id,
                recovery_keypair=recovery_keypair,
                wa_fb_password=fb_password,
            )

            # ── Step 3: Send PeerDataOperation response to companion ──
            # After WWWGetNonceForCompanionDevice succeeds, the primary must push
            # the nonce + waFbid to the companion via a protocol_message so the
            # companion can complete its canonical login.
            #
            # IMPORTANT: The message can only be sent AFTER an axolotl session is
            # established with the companion. The session is established when the
            # account_sync notification arrives and GetKeysIqProtocolEntity fetches
            # the companion's prekeys. We store the nonce+fbid and let the
            # account_sync handler send the message once the session is ready.
            if companion_nonce:
                # Store for deferred sending by pairing.handle_account_sync_notification.
                # The PeerDataOperation response can only be sent after an axolotl
                # session is established with the companion (via GetKeys in
                # account_sync handler). Do NOT send immediately here — that would
                # trigger a redundant GetKeys request before account_sync arrives.
                bot.botLayer.getStack().setProp("pair-companion-nonce", companion_nonce)
                bot.botLayer.getStack().setProp("pair-companion-fbid", fbid)
                logger.info(f"Stored companion nonce for deferred send "
                            f"(will send in account_sync handler after session "
                            f"with {companionJid} is established)")
            else:
                logger.warning("No companion_nonce — skipping PeerDataOperation response")

            return self.success(
                deviceJid=result.deviceJid,
                companionProps=Utils.b64str(result.companionProps),
                companionNonce=companion_nonce,
            )

        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))

    async def _send_nonce_for_companion(
        self,
        device_id: int,
        fbid: str,
        encryption_pem: Optional[str],
        password_pem: Optional[str],
        password_pem_key_id: Optional[int],
        recovery_keypair,
        wa_fb_password: Optional[str] = None,
    ) -> Optional[str]:
        """Call WWWGetNonceForCompanionDevice to fetch the companion canonical nonce.

        Implementation based on APK CompanionCanonicalUserNonceManager.A00:
          1. C40074Hmy.A00() builds encrypted_password from canonical certs:
             - PWD_WA hash with password_pem + key_id
             - plaintext {version:1, timestamp, password, client_pub_key, ...}
             - encrypt_with_cert(encryption_pem) → {key, data, tag, nonce}
             - G4h.A0z adds "nonce" + "algorithm":"rsa2048" to encrypted_password
          2. G4h.A0m() generates a random AES-256 SecretKey
          3. nonce_encryption_key = Base64.encodeToString(
               AbstractC35641ij.A1b(G4d.A0x(secretKey.getEncoded(), 0)), 0)
             = double-base64(random AES key bytes)
          4. Query input fields (NO use_case):
             device_id, fbid, nonce_encryption_key, encrypted_password,
             request_id, registration_trace_id
          5. Response: data.xwa2_ent_get_canonical_ent_device_nonce.encrypted_nonce
             = {key, data, tag, nonce} — AES-GCM encrypted with the SAME random AES key
          6. ID8.A01 decrypts with the random AES SecretKey (NOT RSA keypair)
             → JSON {"data": "{\"nonce\":\"xxx\"}"} → parse inner JSON → nonce string

        Returns:
            The decrypted companion nonce string, or None on failure.
        """
        from app.layer.canonical_credentials import (
            build_pwd_wa_hash, encrypt_with_cert, _b64_dfl,
        )
        from Crypto.Cipher import AES
        from Crypto.Random import get_random_bytes

        if not encryption_pem or not password_pem or not recovery_keypair:
            logger.error("WWWGetNonceForCompanionDevice: missing canonical cert data "
                         f"(encryption_pem={bool(encryption_pem)}, "
                         f"password_pem={bool(password_pem)}, "
                         f"recovery_kp={bool(recovery_keypair)})")
            return None

        if not fbid:
            logger.warning("WWWGetNonceForCompanionDevice: fbid is empty, "
                           "server may reject the request")

        if password_pem_key_id is None:
            logger.error("WWWGetNonceForCompanionDevice: password_pem_key_id is None")
            return None

        # Step 1: PWD_WA hash using WaFbPassword (NOT random password!)
        # APK C40074Hmy.A01: str3 = c15470nz.A05.A00 = "WaFbPassword"
        # This is the password stored from WWWExchangeNonceForAccessToken flow.
        # Using a random password here causes 500 Internal Server Error.
        raw_pwd = wa_fb_password
        if not raw_pwd:
            logger.error("WWWGetNonceForCompanionDevice: WaFbPassword not available, "
                         "cannot build encrypted_password. Need to run exchange flow first.")
            return None
        ts = int(time.time())

        pwd_hash = build_pwd_wa_hash(
            password=raw_pwd,
            key_id=password_pem_key_id,
            pubkey_pem=password_pem,
            timestamp=ts,
        )

        # Step 2: plaintext JSON (canonical format from C40074Hmy.A01)
        # client_pub_key = password_pem string (the str parameter in A01)
        plaintext = _json.dumps({
            "version": 1,
            "timestamp": ts,
            "password": pwd_hash,
            "client_pub_key": password_pem,
            "client_pub_key_type": "RSA 2048",
        }, separators=(",", ":"))

        # Step 3: encrypt plaintext with encryption_pem cert
        enc_key, ctxt, tag, iv = encrypt_with_cert(plaintext, encryption_pem)
        logger.info(f"WWWGetNonceForCompanionDevice: plaintext={len(plaintext)}B, "
                    f"ctxt={len(ctxt)}B, enc_key={len(enc_key)}B")

        # Step 4: generate random AES-256 key (G4h.A0m)
        # This key encrypts the response nonce — NOT the recovery RSA keypair
        nonce_aes_key = get_random_bytes(32)

        # Step 5: nonce_encryption_key = double-base64(AES key)
        # Java: G4d.A0x(key, 0) → Base64.encodeToString(key, 0) = wrapped base64 with trailing \n
        #       AbstractC35641ij.A1b(str) → str.getBytes() (NO extra newline, just UTF-8 bytes)
        #       Base64.encodeToString(result, 0) → outer wrapped base64 with trailing \n
        # So: outer = Base64.DEFAULT( Base64.DEFAULT(aes_key).getBytes() )
        nonce_enc_key_inner = _b64_dfl(nonce_aes_key).encode("utf-8")
        nonce_enc_key_outer = _b64_dfl(nonce_enc_key_inner)  # keep trailing \n (Base64.DEFAULT)

        # Step 6: build query — encrypted_password has "algorithm":"rsa2048"
        # (G4h.A0z adds it). NO use_case field (not in APK code).
        reg_trace = getattr(self.bot.botLayer, '_recovery_trace_id', str(uuid.uuid4()))
        query = {
            "variables": {
                "input": {
                    "device_id": device_id,
                    "encrypted_password": {
                        "algorithm": "rsa2048",
                        "key": _b64_dfl(enc_key),
                        "data": _b64_dfl(ctxt),
                        "tag": _b64_dfl(tag),
                        "nonce": _b64_dfl(iv),
                    },
                    "fbid": fbid,
                    "nonce_encryption_key": nonce_enc_key_outer,
                    "registration_trace_id": reg_trace,
                    "request_id": str(uuid.uuid4()),
                }
            }
        }

        try:
            wmex_entity = WmexQueryIqProtocolEntity(
                query_name="WWWGetNonceForCompanionDevice", query_obj=query
            )
            # WmexResultIqProtocolEntity auto-decodes argo response via
            # ArgoMessageDecoder — no manual argo parsing needed.
            nonce_result = await self.send_iq_expect(
                wmex_entity, WmexResultIqProtocolEntity
            )
            result_obj = nonce_result.result_obj
            logger.info(f"WWWGetNonceForCompanionDevice RAW: "
                        f"{_json.dumps(result_obj, indent=2)[:4000]}")

            # Step 7: extract encrypted_nonce and decrypt with the random AES key
            # (C38288Gvc case 1: ID8.A01(encrypted_nonce, secretKey))
            companion_nonce = self._extract_and_decrypt_nonce(
                result_obj, nonce_aes_key
            )

            if companion_nonce:
                self.bot.botLayer._companion_nonce = companion_nonce
                logger.info(f"WWWGetNonceForCompanionDevice: decrypted nonce="
                            f"{companion_nonce[:40]}...")
            else:
                logger.warning("WWWGetNonceForCompanionDevice: no nonce found/decrypted")

            return companion_nonce

        except Exception as e:
            logger.warning(f"WWWGetNonceForCompanionDevice failed ({e}), "
                           f"Web may not progress")
            return None

    def _extract_and_decrypt_nonce(self, result_obj, nonce_aes_key: bytes) -> Optional[str]:
        """Extract encrypted_nonce from the argo-decoded response and decrypt it.

        APK C38288Gvc case 1 + ID8.A01:
          - encrypted_nonce = {key, data, tag, nonce} from
            data.xwa2_ent_get_canonical_ent_device_nonce.encrypted_nonce
          - C39536HdS constructor: (key→A01, data→A00, tag→A03, nonce→A02)
          - ID8.A01 uses:
            A00 ("data" field)  = ciphertext (encrypted nonce data)
            A02 ("nonce" field) = IV/nonce for AES-GCM
            A03 ("tag" field)   = GCM auth tag
            A01 ("key" field)   = unused (AES key is the random one we sent)
          - AES-GCM decrypt with the random AES-256 key (nonce_aes_key)
          - Result: JSON {"data":"{\"nonce\":\"xxx\"}"} → parse inner → nonce
        """
        from Crypto.Cipher import AES

        def find_encrypted_nonce(obj, depth=0):
            if depth > 10:
                return None
            if isinstance(obj, dict):
                if "encrypted_nonce" in obj:
                    val = obj["encrypted_nonce"]
                    if isinstance(val, dict):
                        return val
                    if isinstance(val, list) and val and isinstance(val[0], dict):
                        return val[0]
                for k, v in obj.items():
                    r = find_encrypted_nonce(v, depth + 1)
                    if r:
                        return r
            elif isinstance(obj, list):
                for item in obj:
                    r = find_encrypted_nonce(item, depth + 1)
                    if r:
                        return r
            return None

        enc_nonce = find_encrypted_nonce(result_obj)
        if not enc_nonce:
            logger.warning("encrypted_nonce field not found in response")
            return None

        try:
            def _as_bytes(val):
                if isinstance(val, (bytes, bytearray)):
                    return bytes(val)
                if isinstance(val, str):
                    cleaned = "".join(val.split())
                    return base64.b64decode(cleaned)
                return None

            # Standard field mapping (confirmed from C39536HdS constructor):
            #   constructor(key, data, tag, nonce) → A01=key, A00=data, A03=tag, A02=nonce
            #   ID8.A01: A00=data(ciphertext), A02=nonce(IV), A03=tag(auth_tag), A01=key(unused)
            ciphertext = _as_bytes(enc_nonce.get("data"))
            iv = _as_bytes(enc_nonce.get("nonce"))
            auth_tag = _as_bytes(enc_nonce.get("tag"))

            if not all([ciphertext, iv is not None, auth_tag is not None]):
                logger.warning(f"encrypted_nonce missing fields: "
                               f"data={bool(ciphertext)}, "
                               f"nonce(IV)={iv is not None}, "
                               f"tag={auth_tag is not None}")
                return None

            logger.debug(f"encrypted_nonce: data={len(ciphertext)}B, "
                         f"nonce(IV)={len(iv)}B, tag={len(auth_tag)}B")

            # ID8.A01: AES-GCM decrypt with the random AES key we sent.
            # Java: doFinal(ciphertext + tag) → PyCryptodome: decrypt_and_verify(ctxt, tag)
            cipher = AES.new(nonce_aes_key, AES.MODE_GCM, nonce=iv)
            decrypted = cipher.decrypt_and_verify(ciphertext, auth_tag).decode("utf-8")
            logger.info(f"WWWGetNonceForCompanionDevice: decrypted plaintext="
                        f"{decrypted[:200]}")

            # APK: AbstractC73223Pe.A14(ID8.A01(...).getString("data"))
            # = JSON.parse(outerJSON.getString("data"))
            # outer JSON = {"data": "{\"nonce\":\"xxx\"}"}
            outer = _json.loads(decrypted)
            if isinstance(outer, dict) and "data" in outer:
                inner = _json.loads(outer["data"])
                if isinstance(inner, dict):
                    nonce = inner.get("nonce", "")
                    if nonce:
                        return str(nonce)

            # Fallback: if decrypted is directly {"nonce":"xxx"}
            if isinstance(outer, dict):
                nonce = outer.get("nonce", "")
                if nonce:
                    return str(nonce)

            # Last resort: treat the string itself as the nonce
            return decrypted.strip() or None

        except Exception as e:
            logger.error(f"Failed to decrypt encrypted_nonce: {e}")
            return None

    async def _send_peer_data_op_response(
        self, companion_jid: str, nonce: str, fbid: str,
    ):
        """Send PeerDataOperationRequestResponseMessage to the companion.

        After WWWGetNonceForCompanionDevice succeeds, the primary pushes the
        nonce + waFbid to the companion so it can complete canonical login:

          protocol_message {
            type: PEER_DATA_OPERATION_REQUEST_RESPONSE_MESSAGE
            peer_data_operation_request_response_message {
              peerDataOperationResult {
                companionCanonicalUserNonceFetchRequestResponse {
                  nonce: "..."
                  waFbid: "..."
                  forceRefresh: false
                }
              }
            }
          }
        """
        from proto.e2e_pb2 import Message as ProtoMessage
        from core.layers.protocol_messages.protocolentities import (
            ProtocolMessageProtocolEntity,
        )
        from core.layers.protocol_messages.protocolentities.attributes import (
            ProtocolAttributes, MessageMetaAttributes,
        )

        logger.info(f"Sending PeerDataOperation response to {companion_jid}: "
                    f"nonce={nonce[:20] if nonce else ''}..., fbid={fbid}")

        # Build the response proto
        resp_msg = ProtoMessage()
        resp_msg.protocol_message.type = \
            ProtoMessage.ProtocolMessage.PEER_DATA_OPERATION_REQUEST_RESPONSE_MESSAGE
        pr = resp_msg.protocol_message.peer_data_operation_request_response_message

        result = pr.peerDataOperationResult.add()
        resp = result.companionCanonicalUserNonceFetchRequestResponse
        if nonce:
            resp.nonce = nonce
        if fbid:
            resp.waFbid = fbid
        resp.forceRefresh = False

        # Wrap in ProtocolMessageProtocolEntity and send to companion
        resp_entity = ProtocolMessageProtocolEntity(
            protocol_attr=ProtocolAttributes(
                type=ProtocolAttributes.TYPE_PEER_DATA_OPERATION_REQUEST_RESPONSE_MESSAGE,
                peer_data_operation_request_response_message=pr,
            ),
            message_meta_attributes=MessageMetaAttributes(
                recipient=companion_jid, category="peer"
            ),
        )
        # Set raw protobuf bytes (overrides AttributesConverter re-encoding)
        resp_entity.raw = resp_msg.SerializeToString()
        await self.bot.botLayer.toLower(resp_entity)
        logger.info("PeerDataOperation response sent to companion")