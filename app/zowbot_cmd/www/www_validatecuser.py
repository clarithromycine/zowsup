"""WWWValidateCanonicalUser — test encrypted_password independently from exchange flow."""

import logging
import json
from datetime import datetime
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import WmexQueryIqProtocolEntity
from app.layer.canonical_credentials import (
    _rand_pwd, _jj5_a01, build_pwd_wa_hash, encrypt_with_cert, _b64_dfl,
)

logger = logging.getLogger(__name__)


class Cmd_WWW_ValidateUser(BotCommand):

    COMMAND = "www.validateuser"
    DESCRIPTION = "Validate WWW canonical user (test encrypted_password)"

    async def execute(self, params, options):
        layer = self.bot.botLayer

        # Step 1: trigger → get fbid + certs
        from app.layer.canonical_credentials import trigger_account_recovery
        fb_result = await trigger_account_recovery(layer)
        if not fb_result:
            return self.fail(error="trigger failed")
        fb_id = fb_result["fb_id"]
        logger.info(f"validate: fbid={fb_id}")

        encryption_pem = getattr(layer, "_www_encryption_pem", None)
        password_pem = getattr(layer, "_fb_password_pem", None)
        password_pem_key_id = getattr(layer, "_fb_password_pem_key_id", None) 
        recovery_kp = getattr(layer, "_recovery_keypair", None)
        use_case = "CANONICAL"

        if not encryption_pem or not password_pem or not recovery_kp:
            return self.fail(error="cert data not available")

        logger.info(f"validate: use_case={use_case}, key_id={password_pem_key_id}")

        # Step 2: generate encrypted_password (same logic as exchange)
        raw_pwd = _rand_pwd()
        ts = int(datetime.now().timestamp())
        client_pub = _jj5_a01(recovery_kp.publickey())
        pwd_hash = build_pwd_wa_hash(raw_pwd, key_id=password_pem_key_id,
                                      pubkey_pem=password_pem, timestamp=ts)

        plaintext = json.dumps({
            "version": 1,
            "timestamp": ts,
            "password": pwd_hash,
            "client_pub_key": client_pub,
            "client_pub_key_type": "RSA 2048",
        }, separators=(",", ":"))

        enc_key, ctxt, tag, iv = encrypt_with_cert(plaintext, encryption_pem)
        logger.info(f"validate: plaintext={len(plaintext)}B, ctxt={len(ctxt)}B, "
                    f"enc_key={len(enc_key)}B, tag={len(tag)}B, iv={len(iv)}B")

        # Step 3: send WWWValidateCanonicalUser
        query = {
            "variables": {
                "input": {
                    "encrypted_password": {
                        "algorithm": "rsa2048",
                        "data": _b64_dfl(ctxt),
                        "key": _b64_dfl(enc_key),
                        "nonce": _b64_dfl(iv),
                        "tag": _b64_dfl(tag),
                    },
                    "fbid": fb_id,
                }
            }
        }

        entity = WmexQueryIqProtocolEntity(query_name="WWWValidateCanonicalUser", query_obj=query)
        try:
            result = await layer._sendIqAsync(entity)
            rj = getattr(result, "result_obj", None) or {}
            logger.info(f"validate: response={rj}")
            return self.success(result=rj)
        except Exception as e:
            logger.error(f"validate error: {e}")
            return self.fail(error=str(e))
