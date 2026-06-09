"""NotificationHandler — server push notification dispatch."""

import logging

from proto import zowsup_pb2
from core.layers.protocol_ib.protocolentities import *
from core.layers.protocol_notifications.protocolentities import *
from core.layers.protocol_groups.protocolentities import *
from core.layers.protocol_presence.protocolentities.presence import PresenceProtocolEntity

logger = logging.getLogger(__name__)


class NotificationHandler:
    """Handles all server push notifications and IB protocol entities."""

    def __init__(self, layer):
        """
        Args:
            layer: ZowBotLayer instance
        """
        self.layer = layer

    # ── Notification dispatch ───────────────────────────────────────────────

    async def on_notification(self, entity):
        """Dispatch incoming notifications by type."""

        if isinstance(entity, MexUpdateNotificationProtocolEntity):
            self.layer.logger.info(
                "Notification: Received a MexUpdate Notification: {}".format(entity.jsonObj)
            )
            return

        if isinstance(entity, ServerPushConfigNotificationProtocolEntity):
            self.layer.logger.info("Notification: Received a ServerPushConfig Notification")
            await self.layer.executeCommand("misc.regfcm", [], {})
            return

        if isinstance(entity, ServerSyncNotificationProtocolEntity):
            collectionNames = []
            if entity.collections is not None:
                for item in entity.collections:
                    collectionNames.append(item["name"])
            self.layer.logger.info(
                "Notification: Received a ServerSync Notification, collections={}".format(
                    ",".join(collectionNames)
                )
            )
            try:
                await self.layer.syncData([",".join(collectionNames)], {})
            except Exception as e:
                self.layer.logger.warning("syncData failed, continuing: {}".format(e))

        if isinstance(entity, AccountSyncNotificationProtocolEntity):
            await self.layer.pairing.handle_account_sync_notification(entity)

        if isinstance(entity, LinkCodeCompanionRegNotificationProtocolEntity):
            await self.layer.pairing.handle_linkcode_notification(entity)

        if isinstance(entity, WaOldCodeNotificationProtocolEntity):
            self.layer.logger.info(
                "Notification: Received a wa_old registration code: {} in {}".format(
                    entity.code, entity.timestamp
                )
            )
            if self.layer.getProp("TRANSFER6_MODE", False):
                if int(entity.timestamp) >= self.layer.bot.startts:
                    self.layer.bot.wa_old = entity.code
                    self.layer.callback(
                        modeResult={"retcode": 0, "code": entity.code}
                    )
            return

        if isinstance(entity, DeviceLogoutNotificationProtocolEntity):
            self.layer.logger.info(
                f"Notification: device_logout request from {entity.device} "
                f"with refId = {entity.refId} in {entity.timestamp}"
            )
            self.layer.logoutApprove([entity.refId], {})
            return

        if isinstance(entity, CreateGroupsNotificationProtocolEntity):
            self.layer.logger.info(
                "Notification: Group {} created".format(entity.groupId)
            )
            return

        if isinstance(entity, AddGroupsNotificationProtocolEntity):
            self.layer.logger.info(
                "Notification: Group {} add participant {}".format(
                    entity.getGroupId(), entity.getParticipants()[0]
                )
            )
            return

        if isinstance(entity, RemoveGroupsNotificationProtocolEntity):
            self.layer.logger.info(
                "Notification: Group {} remove participant {}".format(
                    entity.getGroupId(), entity.getParticipants()[0]
                )
            )
            return

        if isinstance(entity, SetPictureNotificationProtocolEntity):
            if entity.setJid is not None:
                self.layer.callback(
                    event={
                        "event": zowsup_pb2.BotEvent.Event.CONTACT_UPDATE,
                        "detail": {
                            "target": entity.setJid,
                            "key": "AVATAR",
                            "value": entity.setId,
                        },
                    }
                )
            return

        if isinstance(entity, BusinessNameUpdateNotificationProtocolEntity):
            if entity.name is not None:
                if entity.jid.endswith("@lid"):
                    self.layer.db._store.updateContact(
                        None, lid=entity.jid, name=entity.name
                    )
                else:
                    self.layer.db._store.updateContact(
                        jid=entity.jid, lid=None, name=entity.name
                    )

                self.layer.callback(
                    event={
                        "event": zowsup_pb2.BotEvent.Event.CONTACT_UPDATE,
                        "detail": {
                            "target": entity.jid,
                            "key": "NAME",
                            "value": entity.name,
                        },
                    }
                )
            return

    # ── IB protocol ─────────────────────────────────────────────────────────

    async def on_ib(self, entity):
        """Handle incoming IB (interactive broadcast) protocol entities."""

        if isinstance(entity, GpiaRequestIbProtocolEntity):
            self.layer.logger.info("Ib-gpia-request: {}".format(entity.nonce))
            await self.layer.gpia([entity.nonce], {})

        if isinstance(entity, SafetynetRequestIbProtocolEntity):
            self.layer.logger.info("Ib-safetynet-request: {}".format(entity.nonce))
            await self.layer.safetynet([entity.nonce], {})

    # ── Presence ────────────────────────────────────────────────────────────

    def on_presence(self, entity):
        """Handle presence protocol entities."""
        if isinstance(entity, PresenceProtocolEntity):
            self.layer.setCmdResult(
                entity.getId(),
                {"type": entity.getType(), "last": entity.getLast()},
            )
            return
