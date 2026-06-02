"""newsletter.metadata command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import WmexQueryIqProtocolEntity, WmexResultIqProtocolEntity

logger = logging.getLogger(__name__)


class Cmd_Newsletter_Metadata(BotCommand):

    COMMAND = "newsletter.metadata"
    DESCRIPTION = "Get newsletter metadata"


    async def execute(self, params, options):

        try:
            query = {
                "variables": {
                    "fetch_creation_time": True,
                    "fetch_description": True,
                    "fetch_handle": True,
                    "fetch_image": True,
                    "fetch_invite": True,
                    "fetch_name": True,
                    "fetch_preview": True,
                    "fetch_settings": True,
                    "fetch_state": True,
                    "fetch_subscribers_count": True,
                    "fetch_verification": True,
                    "fetch_viewer_metadata": False,
                    "fetch_wamo_sub": False,
                    "input": {
                        "key": params[0],
                        "type": "JID",
                        "view_role": "GUEST"
                    }
                }
            }
            entity = WmexQueryIqProtocolEntity(query_name="NewsletterMetadata", query_obj=query)
            entity_result = await self.send_iq_expect(entity, WmexResultIqProtocolEntity)

            return self.success(
                result = entity_result.result_obj
            )


        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))   


