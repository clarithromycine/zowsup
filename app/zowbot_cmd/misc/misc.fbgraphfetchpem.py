"""fbgraphfetchpem command - fetch FB GraphQL PEM certificates for exchange encryption"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities.fb.fb_graphql_fetch_pem import (
    FbGraphqlFetchPem,
    ResultFbGraphqlFetchPemIqProtocolEntity,
)

logger = logging.getLogger(__name__)


class Cmd_Misc_FbGraphFetchPem(BotCommand):

    COMMAND = "misc.fbgraphfetchpem"
    DESCRIPTION = "Fetch FB GraphQL PEM certificates for exchange encryption"

    async def execute(self, params, options):
        try:
            entity = FbGraphqlFetchPem(use_case="CANONICAL")
            result = await self.send_iq_expect(entity, ResultFbGraphqlFetchPemIqProtocolEntity)

            # Store on layer for exchange_nonce_for_token to use
            layer = self.bot.botLayer
            if result.password_pem:
                layer._fb_password_pem = result.password_pem
                logger.info(f"fbgraphfetchpem: stored password_pem (key_id={result.password_pem_key_id})")
            if result.password_pem_key_id:
                layer._fb_password_key_id = int(result.password_pem_key_id)
            if result.encryption_pem:
                layer._fb_encryption_pem = result.encryption_pem

            return self.success(
                algorithm=result.algorithm,
                version=result.version,
                encryption_pem=result.encryption_pem,
                signature_pem=result.signature_pem,
                password_pem=result.password_pem,
                password_pem_key_id=result.password_pem_key_id,
                password_pem_ttl=result.password_pem_ttl,

            )
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))