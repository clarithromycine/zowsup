"""ContactManager — contact synchronization and pre-send assurance."""

import logging

from core.common.tools import Jid
from core.layers.protocol_contacts.protocolentities import (
    ContactGetSyncIqProtocolEntity,
    ContactResultSyncIqProtocolEntity,
)
from core.layers.protocol_iq.protocolentities import WmexQueryIqProtocolEntity, WmexResultIqProtocolEntity

logger = logging.getLogger(__name__)


class ContactManager:
    """Handles contact lookups, synchronization, and pre-send contact assurance."""

    def __init__(self, layer):
        """
        Args:
            layer: ZowBotLayer instance
        """
        self.layer = layer

    async def assure_contacts_and_send(self, cmdParams, options, send_func, redo_func):
        """Ensure target is in contacts before sending, then send."""
        to, *other = cmdParams
        isCompanion = "_" in self.layer.bot.botId
        jid = Jid.normalize(to)
        if jid.endswith("@g.us"):
            # Group JIDs need no contact-sync — send directly
            await send_func(cmdParams, options)
        elif not jid.endswith("@lid"):
            foundContact = self.layer.db._store.findContact(jid)
            if not foundContact and not isCompanion:
                entity = ContactGetSyncIqProtocolEntity([to], mode="delta")
                result_dict = await self.layer._sendIqAsync(entity)
                if isinstance(result_dict["result"], ContactResultSyncIqProtocolEntity):
                    logger.info("add target to contacts")

                    jid_list = []
                    for key, value in result_dict["result"].result.items():
                        if value["type"] == "in":
                            self.layer.db._store.updateContact(value["jid"], value["lid"], key)
                            jid_list.append(value["jid"])
                        else:
                            logger.info("{} not found".format(key))
                    if len(jid_list) > 0:
                        cmdParams[0] = ",".join(jid_list)
                        await redo_func(cmdParams, options)
                    else:
                        logger.error("target not found in contacts")
                else:
                    logger.error("ERROR on _sendIq")

            else:
                logger.info("target in contacts")
                await send_func(cmdParams, options)
        else:
            logger.info("lid-target, direct send")
            await send_func(cmdParams, options)

    async def get_contact_list(self, cmdParams, options):
        """Query the full contact list via WmexQuery."""
        query = {
            "variables": {
                "batch_size": 3000,
                "include_encrypted_metadata_v2": False,
                "include_lid_info": True,
                "input": {
                    "query_input": [{"jid": Jid.normalize(cmdParams[0])}],
                    "telemetry": {"context": "REGISTRATION"},
                },
            }
        }
        entity = WmexQueryIqProtocolEntity(query_name="SelfContactsQuery", query_obj=query)
        try:
            result_dict = await self.layer._sendIqAsync(entity)
            entity_result = result_dict["result"]

            if isinstance(entity_result, WmexResultIqProtocolEntity):
                return {"result": entity_result.result_obj}
            else:
                raise Exception(f"Unexpected response type: {type(entity_result)}")
        except Exception as e:
            logger.error(f"getContactList error: {e}")
            raise

    def get_context_value(self, ctxId, key):
        """Get a value from the context map by ctxId and key."""
        if ctxId not in self.layer.ctxMap:
            return None
        if key not in self.layer.ctxMap[ctxId]:
            return None
        return self.layer.ctxMap[ctxId][key]
