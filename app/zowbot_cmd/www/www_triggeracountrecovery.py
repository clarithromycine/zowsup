"""WWWTriggerAcountRecovery command — get canonical fb_id + access_token.

Full flow:
  1. trigger_account_recovery → fbid (saves KeyPair to layer._recovery_keypair)
  2. Wait for server to push recovery_nonce (via ib node, saved to layer._recovery_nonce)
  3. exchange_nonce_for_token → RSA-OAEP decrypt nonce → WWWGetCertificates →
     PWD_WA hash → ID8.A06 encrypt → WWWExchangeNonceForAccessToken → access_token
"""

import asyncio
import logging

from app.zowbot_cmd.base import BotCommand
from app.layer.canonical_credentials import (
    trigger_account_recovery,
    exchange_nonce_for_token,
)

logger = logging.getLogger(__name__)

class Cmd_WWW_TrigerAcountRecovery(BotCommand):

    COMMAND = "www.triggeracountrecovery"  # 拼写来源于 WA 源码，保留
    DESCRIPTION = "Get canonical fb_id + access_token"

    async def execute(self, params, options):
        try:
            # Step 1: trigger → fbid
            fb_result = await trigger_account_recovery(self.bot.botLayer)
            if not fb_result:
                return self.fail(error="trigger_account_recovery returned None")
            fb_id = fb_result["fb_id"]

            # Step 2: wait for recovery_nonce (server pushes via ib node)
            nonce = await self._wait_for_nonce(self.bot.botLayer, timeout=5)
            if not nonce:
                return self.success(result={"fb_id": fb_id, "access_token": None,
                    "msg": "fbid obtained, nonce not received (timeout)"})
            
            # Step 3: exchange nonce → access_token
            token_result = await exchange_nonce_for_token(self.bot.botLayer, nonce)
            if token_result:                                
                self._persist_fbinfo(token_result)
                return self.success(result=token_result)
            else:
                return self.success(result={"fb_id": fb_id, "access_token": None,
                    "msg": "fbid obtained, exchange failed"})

        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))

    async def _wait_for_nonce(self, layer, timeout=15):
        """Poll canonical_credentials._pending_nonce until set or timeout."""
        import app.layer.canonical_credentials as cc

        for _ in range(timeout * 2):
            if cc._pending_nonce:
                nonce = cc._pending_nonce
                cc._pending_nonce = None  # consume it
                return nonce
            await asyncio.sleep(0.5)
        return None

    def _persist_fbinfo(self, fbinfo):
        try:
            layer = self.bot.botLayer
            profile = layer.getStack().getProp("profile")
            if profile and profile.config:
                profile.config.fbinfo = fbinfo
                profile.write_config()
            if hasattr(layer, 'pairing'):
                layer.pairing.wa_fbid = fbinfo["fb_id"]
            layer._fbid = fbinfo["fb_id"]
        except Exception as e:
            logger.warning(f"Failed to persist fbid: {e}")



