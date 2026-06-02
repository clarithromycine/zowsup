"""contact.sync command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_contacts.protocolentities import ContactGetSyncIqProtocolEntity, ContactResultSyncIqProtocolEntity

logger = logging.getLogger(__name__)


class Cmd_Contact_Sync(BotCommand):

    COMMAND = "contact.sync"
    DESCRIPTION = "Sync contacts"


    async def execute(self, params, options):

        if "mode" not in options:
            options["mode"] = "delta"
        if "cnt" not in options:
            options["cnt"] = "30"

        nums = params[0].split(",")
        
        try:
            entity = ContactGetSyncIqProtocolEntity(nums, mode=options["mode"])
            entity_result = await self.send_iq_expect(entity, ContactResultSyncIqProtocolEntity)
            logger.info("add target to contacts")
            for key, value in entity_result.result.items():
                if value["type"] == "in":
                    self.bot.botLayer.db._store.updateContact(value["jid"], value["lid"], key)
            
            return self.success(
                result = entity_result.result
            )
        except Exception as e:
            logger.error(f"syncContacts error: {e}")
            return self.fail(error=str(e))


