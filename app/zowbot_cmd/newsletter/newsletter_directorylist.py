"""newsletter.directorylist command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import WmexQueryIqProtocolEntity, WmexResultIqProtocolEntity

logger = logging.getLogger(__name__)


class Cmd_Misc_Directorylist(BotCommand):
    
    COMMAND = "newsletter.directorylist"
    DESCRIPTION = "Directory list newsletter"


    async def execute(self, params, options):

        try:
            category = params[0] if len(params) > 0 else None
            offset = params[1] if len(params) > 1 else 0
            limit = params[2] if len(params) > 2 else 50
            
            query = {
                "variables": {
                    "input": {
                        "filters": {
                            "categories": [category] if category else [],
                            "country_codes": ["PH"]
                        },
                        "limit": limit,
                        "session_fields": {
                            "discovery_surface": "channel_directory_categories",
                            "query_id": None,
                            "search_id": None,
                            "updates_tab_session_id": "3442139553891945124"
                        },
                        "start_cursor": None if offset == 0 else str(offset),
                        "view": "RECOMMENDED"
                    }
                }
            }
            
            entity = WmexQueryIqProtocolEntity(
                query_name="NewsletterDirectoryList",
                query_obj=query
            )
            result = await self.send_iq_expect(entity, WmexResultIqProtocolEntity)

            items = []
            data = result.getData()
            
            if isinstance(data, dict):
                for item in data.get("items", []):
                    items.append({
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "description": item.get("description"),
                        "category": item.get("category"),
                        "subscribers": item.get("subscribers"),
                        "avatar": item.get("avatar"),
                        "verified": item.get("verified")
                    })
            
            return self.success(   
                items=items,
                count=len(items),
                totalCount=data.get("totalCount") if isinstance(data, dict) else None
            )

        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))   

