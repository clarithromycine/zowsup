"""SyncManager — app state sync, FCM, device logout, and key generation."""

import asyncio
import base64
import logging
import random
import time

from axolotl.ecc.curve import Curve
from core.layers import YowLayerEvent
from core.layers.network.layer import YowNetworkLayer
from core.layers.protocol_historysync.protocolentities.attributes import *
from core.layers.protocol_iq.protocolentities import (
    AppSyncResetIqProtocolEntity,
    AppSyncStateIqProtocolEntity,
    ResultAppSyncStateIqResponseProtocolEntity,
    PushGetCatIqProtocolEntity,
    PushGetCatResultIqProtocolEntity,
    AccountLogoutApproveIqProtocolEntity,
)

logger = logging.getLogger(__name__)


class SyncManager:
    """Handles app state synchronization, FCM registration, and device management."""

    def __init__(self, layer):
        """
        Args:
            layer: ZowBotLayer instance
        """
        self.layer = layer

    async def sync_data(self, cmdParams, options):
        """Sync app state data with the server (used by companion devices)."""
        request = {}
        collectionNames = cmdParams[0].split(",")
        for name in collectionNames:
            request[name] = {
                "version": "0",
                "return_snapshot": True,
            }

        entity = AppSyncStateIqProtocolEntity(request=request)
        try:
            while entity is not None:
                result_dict = await self.layer._sendIqAsync(entity)
                entity_result = result_dict["result"]
                if isinstance(entity_result, ResultAppSyncStateIqResponseProtocolEntity):
                    requestNext = {}
                    for key, item in entity.collections.items():
                        if "error" in item and item["error"]["code"] == "409":
                            requestNext[key] = {
                                "version": str(int(entity.request[key]["version"]) + 1),
                            }
                        else:
                            # Non-conflicting data — companion doesn't decrypt yet
                            pass

                    if len(requestNext) > 0:
                        entity = AppSyncStateIqProtocolEntity(request=requestNext)
                        continue
                    else:
                        entity = None
                else:
                    raise Exception(f"Unexpected response type: {type(entity_result)}")

        except asyncio.TimeoutError as e:
            logger.warning("syncData timeout (collections={}): {}".format(cmdParams[0], e))
        except Exception as e:
            logger.error("syncData error: {}".format(e), exc_info=True)

    async def reset_sync(self, params, options):
        """Reset app state sync."""
        try:
            entity = AppSyncResetIqProtocolEntity()
            await self.layer.toLower(entity)
            logger.info("resetSync ok")
        except Exception as e:
            logger.error(f"resetSync error: {e}")
            raise

    def generate_app_state_sync_keys(self, n):
        """Generate n AppStateSyncKey attributes for companion pairing."""
        profile = self.layer.getStack().getProp("profile")
        keys = []
        for i in range(0, n):
            key = AppStateSyncKeyAttribute(
                key_id=AppStateSyncKeyIdAttribute(
                    key_id=random.randint(10000, 20000).to_bytes(6, "big")
                ),
                key_data=AppStateSyncKeyDataAttribute(
                    key_data=Curve.generateKeyPair().publicKey.serialize()[1:],
                    fingerprint=AppStateSyncKeyFingerprintAttribute(
                        raw_id=random.randint(10000, 2000000000),
                        current_index=i,
                        device_indexes=profile.config.device_list,
                    ),
                    timestamp=int(time.time()),
                ),
            )
            keys.append(key)
        return keys

    async def logout_approve(self, cmdParams, options):
        """Approve a device logout request."""
        entity = AccountLogoutApproveIqProtocolEntity(cmdParams[0])
        await self.layer._sendIqAsync(entity)
        return {"retcode": 0}

    async def fcm_msg_callback(self, obj, data, p):
        """Handle FCM push message callback — fetch and store push CAT token."""
        logger.info("fcm msg callback")

        entity = PushGetCatIqProtocolEntity(token=data["pn"])
        result = await self.layer._sendIqAsync(entity)
        print(result)

        result_entity = result.get("result")
        if isinstance(result_entity, PushGetCatResultIqProtocolEntity):
            profile = self.layer.getStack().getProp("profile")
            profile.config.fcm_cat = base64.b64encode(result_entity.catData)
            profile.write_config()
            logger.info("get fcm cat success")
            await self.layer.bot._stack.broadcastEvent(
                YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT)
            )
        else:
            logger.error("get fcm cat failed")
