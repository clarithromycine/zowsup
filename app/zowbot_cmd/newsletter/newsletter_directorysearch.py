"""newsletter.directorysearch command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import WmexQueryIqProtocolEntity, WmexResultIqProtocolEntity
from app.param_not_enough_exception import ParamsNotEnoughException

logger = logging.getLogger(__name__)


class Cmd_Newsletter_Directorysearch(BotCommand):

    COMMAND = "newsletter.directorysearch"
    DESCRIPTION = "Directory search newsletter"


    async def execute(self, params, options):

        if len(params) < 1:
            raise ParamsNotEnoughException()
        
        try:
            search_query = params[0]
            
            query = {
                "variables": {
                    "input": {
                        "filters": {
                            "categories": [],
                            "country_codes": ["PH"]
                        },
                        "limit": 50,
                        "query_string": search_query,
                        "session_fields": {
                            "discovery_surface": "channel_directory_search",
                            "query_id": None,
                            "search_id": None,
                            "updates_tab_session_id": None
                        },
                        "start_cursor": None,
                        "view": "SEARCH"
                    }
                }
            }
            
            entity = WmexQueryIqProtocolEntity(
                query_name="NewsletterDirectorySearch",
                query_obj=query
            )
            entity_result = await self.send_iq_expect(entity, WmexResultIqProtocolEntity)


            results = []
            data = entity_result.getData()
            
            if isinstance(data, dict):
                for item in data.get("items", []):
                    results.append({
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "description": item.get("description"),
                        "subscribers": item.get("subscribers"),
                        "avatar": item.get("avatar"),
                        "verified": item.get("verified")
                    })
            
            return self.success(
                results=results,
                count=len(results),
            )
                
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))   


