"""newsletter.recommended command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import WmexQueryIqProtocolEntity, WmexResultIqProtocolEntity

logger = logging.getLogger(__name__)



class Cmd_Newsletter_Recommended(BotCommand):

    COMMAND = "newsletter.recommended"
    DESCRIPTION = "Get recommended newsletters"


    async def execute(self, params, options):

        try:
            query = {
                "variables": {
                    "input": {
                        "filters": {
                            "categories": [],
                            "country_codes": ["PH"]
                        },
                        "limit": 50,
                        "session_fields": {
                            "discovery_surface": "channel_directory_recommended",
                            "query_id": None,
                            "search_id": None,
                            "updates_tab_session_id": None
                        },
                        "start_cursor": None,
                        "view": "RECOMMENDED"
                    }
                }
            }
            
            entity = WmexQueryIqProtocolEntity(
                query_name="NewsletterRecommended",
                query_obj=query
            )
            entity_result = await self.send_iq_expect(entity, WmexResultIqProtocolEntity)
            newsletters = []
            data = entity_result.getData()            
            if isinstance(data, dict):
                for item in data.get("items", []):
                    newsletters.append({
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "description": item.get("description"),
                        "category": item.get("category"),
                        "subscribers": item.get("subscribers"),
                        "avatar": item.get("avatar"),
                        "verified": item.get("verified")
                    })
            
            return self.success(
                    newsletters=newsletters,
                    count=len(newsletters)
                )
        
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))   

