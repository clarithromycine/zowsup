"""ConnectionManager — connection lifecycle state machine (login/logout/reconnect)."""

import asyncio
import logging
import time

from core.layers import YowLayerEvent
from core.layers.network.layer import YowNetworkLayer
from core.layers.protocol_presence.protocolentities import AvailablePresenceProtocolEntity
from core.common.tools import WATools
from common.utils import Utils
from conf.constants import SysVar
from proto import zowsup_pb2
from app.zowbot_values import ZowBotStatus, ZowBotType

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages connection state, login success/failure, reconnection, and graceful shutdown."""

    def __init__(self, layer):
        """
        Args:
            layer: ZowBotLayer instance
        """
        self.layer = layer

        # Connection state
        self.isConnected = False
        self.detect40x = False
        self.detect503 = False
        self.loginFailCount = 0
        self.loginEventComplete = False
        self.pingCount = 0

    # ── Disconnect / Reconnect ─────────────────────────────────────────────

    async def on_disconnected(self, yowLayerEvent):
        """Handle YowNetworkLayer.EVENT_STATE_DISCONNECTED."""

        # Companion device registration completion
        if self.layer.getProp("jid") is not None:
            if self.layer._qrTask:
                self.layer._qrTask.cancel()
            waNum, a, deviceid = WATools.jidDecode(self.layer.getProp("jid"))
            self.layer.logger.info(
                "Companion device register success({}_{})".format(waNum, deviceid)
            )
            self.layer.setProp("jid", None)
            await asyncio.sleep(3)
            self.layer.getStack().setProfile(
                SysVar.ACCOUNT_PATH + waNum + "_" + str(deviceid)
            )
            await self.layer.getStack().broadcastEvent(
                YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECT)
            )
            return

        # QR refs exhausted — reconnect
        if self.layer.getProp("refs") is not None and len(self.layer.getProp("refs")) == 0:
            await asyncio.sleep(5)
            await self.layer.getStack().broadcastEvent(
                YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECT)
            )
            return

        if self.isConnected:
            self.layer.callback(event={"event": zowsup_pb2.BotEvent.Event.LOGOUT})

        self.isConnected = False

        # Auto-reconnect decision
        if (
            (not self.detect40x)
            and (not self.layer.getProp("USER_REQUEST_QUIT"))
            and self.loginFailCount < 3
            and (not self.layer.bot.quitIfConflict)
        ):
            self.layer.bot.wa_old = None
            self.loginEventComplete = False
            await asyncio.sleep(1)
            await self.layer.getStack().broadcastEvent(
                YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECT)
            )
        else:
            if not self.layer.getProp("HC_MODE"):
                # Preserve CONFLICTED status — don't overwrite with STOPPED
                if self.layer.bot.status != ZowBotStatus.STATUS_CONFLICTED:
                    self.layer.bot.status = ZowBotStatus.STATUS_STOPPED
                self.layer.callback(event={"event": zowsup_pb2.BotEvent.Event.QUIT})
                if self.layer.db:
                    self.layer.db._store.dbConn.close()
                self.layer.setProp("QUITTED", True)
            else:
                # HC mode — just sleep 1s, nothing else
                self.layer.setProp("THREADQUIT", True)
                await asyncio.sleep(1)

    # ── Stream Error ────────────────────────────────────────────────────────

    async def on_stream_error(self, entity):
        """Handle stream:error protocol entity."""
        self.layer.logger.info("Stream Error")
        self.layer.logger.debug(entity)
        self.layer.bot.status = ZowBotStatus.STATUS_ERROR

        if entity.getErrorType() == "conflict":
            self.layer.bot.conflict = True
            self.layer.bot.status = ZowBotStatus.STATUS_CONFLICTED
            self.layer.bot.quitIfConflict = True
            self.layer.callback(
                event={"event": zowsup_pb2.BotEvent.Event.CONFLICT}
            )

        if entity.code is not None:
            if entity.code == "503":
                self.detect503 = True
                await self.layer.bot._stack.broadcastEvent(
                    YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT)
                )

    # ── Login Failure ───────────────────────────────────────────────────────

    def on_failure(self, entity):
        """Handle login failure (403/401/405/404)."""
        self.layer.logger.info("Login Fail")
        self.loginFailCount += 1

        if entity.reason in ("403", "401", "405", "404"):

            self.layer.callback(
                event={
                    "event": zowsup_pb2.BotEvent.Event.LOGIN_FAIL,
                    "detail": entity.reason,
                }
            )

            # Clear botId on login failure for proper state cleanup
            if entity.reason in ["403", "401", "405"]:
                old_botId = self.layer.bot.botId
                self.layer.bot.botId = None
                self.layer.logger.debug(
                    f"Cleared botId due to login failure ({entity.reason}): {old_botId}"
                )

            self.detect40x = True

            if entity.reason != "405" and self.layer.bot.bot_type != ZowBotType.TYPE_RUN_TEMP:
                self.layer.bot.quit()

            self.loginEventComplete = True

            if self.layer.getProp("HC_MODE"):
                self.layer.db._store.identityKeyStore.dbConn.close()
                self.layer.callback(
                    modeResult={"retcode": -1, "detail": reason}
                )

    # ── Login Success ───────────────────────────────────────────────────────

    async def on_success(self, successProtocolEntity):
        """Handle login success: HC/TRANSFER6 modes, profile save, presence broadcast."""

        if self.layer.getProp("HC_MODE"):
            self.layer.db._store.identityKeyStore.dbConn.close()
            self.layer.callback(
                modeResult={
                    "botId": self.layer.bot.botId,
                    "retcode": 0,
                    "detail": None,
                }
            )

        if self.layer.getProp("TRANSFER6_MODE"):
            try:
                await self.layer.executeCommand("account.set2fa", ["", ""])
                await self.layer.executeCommand("account.setemail", [""])
                await self.layer.executeCommand("account.setname")
                await self.layer.executeCommand("account.info", [])
            except Exception as e:
                self.layer.logger.error(f"Failed to execute account setup commands: {e}")

        if self.layer.bot.profile.config.lid is None:
            profile = self.layer.getStack().getProp("profile")
            profile.config.lid = successProtocolEntity.lid
            profile.write_config()

        self.layer.callback(
            event={"event": zowsup_pb2.BotEvent.Event.LOGIN_SUCCESS}
        )

        if self.layer.getProp("REPAIRFCM", False) and not self.layer.getProp(
            "REPAIRFCM_ING", False
        ):
            logger.info("START REPAIRING FCM")
            await self.layer.executeCommand("misc.regfcm", [], {})
            self.layer.setProp("REPAIRFCM_ING", True)

        self.isConnected = True
        self.loginEventComplete = True
        entity = AvailablePresenceProtocolEntity()
        await self.layer.toLower(entity)
        self.layer.bot.status = ZowBotStatus.STATUS_RUNNING
        self.layer.bot.lastOnlineTime = int(time.time())
        self.loginFailCount = 0
