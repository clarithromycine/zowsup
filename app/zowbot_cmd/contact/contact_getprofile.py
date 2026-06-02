"""contact.getprofile command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_contacts.protocolentities import ProfilesGetSyncIqProtocolEntity,ProfilesResultSyncIqProtocolEntity
from core.common.tools import Jid

logger = logging.getLogger(__name__)


class Cmd_Contact_GetProfile(BotCommand):

    COMMAND = "contact.getprofile"
    DESCRIPTION = "Get contact profile"

    async def execute(self, params, options):

        jids = Jid.normalize(params[0]).split(",")

        if "catalogs" not in options:
            options["catalogs"] = ["picture", "status", "name", "lid"]
        else:
            options["catalogs"] = options["catalogs"].split(",")

        try:
            entity = ProfilesGetSyncIqProtocolEntity(jids, catalogs=options["catalogs"])
            result = await self.send_iq_expect(entity, ProfilesResultSyncIqProtocolEntity)

            return self.success(
                    profiles = result.profilesDict,
            )
        except Exception as e:
            logger.error(f"getProfile error: {e}")
            return self.fail(error=str(e))



