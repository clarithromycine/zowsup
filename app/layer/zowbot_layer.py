# ============================================================================
# ZowBotLayer — thin protocol-layer facade
#
# All business logic has been extracted to app/layer/ managers.
# This class retains only:
#   1. YowInterfaceLayer inheritance (required by the protocol stack)
#   2. @ProtocolEntityCallback / @EventCallback delegation
#   3. Public API surface (backward-compatible property accessors + delegation methods)
# ============================================================================

# ============================================================================
# Standard Library Imports
# ============================================================================
import logging
import sys
import os

sys.path.append(os.getcwd())

# ============================================================================
# Core Layer Imports (required for protocol stack registration)
# ============================================================================
from core.layers import EventCallback, YowLayerEvent
from core.layers.interface import YowInterfaceLayer, ProtocolEntityCallback
from core.layers.network.layer import YowNetworkLayer

# ============================================================================
# Manager imports
# ============================================================================
from app.layer.connection import ConnectionManager
from app.layer.iq_manager import IqManager
from app.layer.pairing import PairingManager
from app.layer.message_handler import MessageHandler
from app.layer.notification_handler import NotificationHandler
from app.layer.media import MediaManager
from app.layer.contacts import ContactManager
from app.layer.sync import SyncManager

logger = logging.getLogger(__name__)


class ZowBotLayer(YowInterfaceLayer):
    PROP_MESSAGES = "org.openwhatsapp.zowsup.prop.sendclient.queue"
    PROP_WAAPI = "org.openwhatsapp.zowsup.prop.sendclient.waapi"

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.logger = bot.logger
        self.db = None
        self.mode = None
        self.ctxMap = {}
        self.ackQueue = []
        self.msgMap = {}
        self.cmdEventMap = {}
        self._qrTask = None
        self._avatarTask = None

        self.connection = ConnectionManager(self)
        self.iq_mgr = IqManager(self)
        self.pairing = PairingManager(self)
        self.messages = MessageHandler(self)
        self.notifications = NotificationHandler(self)
        self.media = MediaManager(self)
        self.contacts = ContactManager(self)
        self.sync = SyncManager(self)

    @property
    def detect40x(self):
        return self.connection.detect40x

    @detect40x.setter
    def detect40x(self, value):
        self.connection.detect40x = value

    @property
    def detect503(self):
        return self.connection.detect503

    @detect503.setter
    def detect503(self, value):
        self.connection.detect503 = value

    @property
    def loginEventComplete(self):
        return self.connection.loginEventComplete

    @loginEventComplete.setter
    def loginEventComplete(self, value):
        self.connection.loginEventComplete = value

    @property
    def loginFailCount(self):
        return self.connection.loginFailCount

    @loginFailCount.setter
    def loginFailCount(self, value):
        self.connection.loginFailCount = value

    @property
    def isConnected(self):
        return self.connection.isConnected

    @isConnected.setter
    def isConnected(self, value):
        self.connection.isConnected = value

    @property
    def pingCount(self):
        return self.connection.pingCount

    @pingCount.setter
    def pingCount(self, value):
        self.connection.pingCount = value

    @property
    def pairingStatus(self):
        return self.pairing.status

    @pairingStatus.setter
    def pairingStatus(self, value):
        self.pairing.status = value

    @property
    def pairingCode(self):
        return self.pairing.code

    @pairingCode.setter
    def pairingCode(self, value):
        self.pairing.code = value

    @property
    def companionHelloEntity(self):
        return self.pairing.companion_hello_entity

    @companionHelloEntity.setter
    def companionHelloEntity(self, value):
        self.pairing.companion_hello_entity = value

    @EventCallback(YowNetworkLayer.EVENT_STATE_DISCONNECTED)
    async def onDisconnected(self, yowLayerEvent):
        await self.connection.on_disconnected(yowLayerEvent)

    @ProtocolEntityCallback("success")
    async def onSuccess(self, successProtocolEntity):
        await self.connection.on_success(successProtocolEntity)

    @ProtocolEntityCallback("failure")
    def onFailure(self, entity):
        self.connection.on_failure(entity)

    @ProtocolEntityCallback("stream:error")
    async def onStreamError(self, entity):
        await self.connection.on_stream_error(entity)

    @ProtocolEntityCallback("iq")
    async def onIq(self, entity):
        await self.iq_mgr.on_iq(entity)

    @ProtocolEntityCallback("message")
    async def onMessage(self, messageProtocolEntity):
        await self.messages.on_message(messageProtocolEntity)

    @ProtocolEntityCallback("receipt")
    async def onReceipt(self, entity):
        await self.messages.on_receipt(entity)

    @ProtocolEntityCallback("ack")
    def onAck(self, entity):
        self.messages.on_ack(entity)

    @ProtocolEntityCallback("notification")
    async def onNotification(self, entity):
        await self.notifications.on_notification(entity)

    @ProtocolEntityCallback("ib")
    async def onIb(self, entity):
        await self.notifications.on_ib(entity)

    @ProtocolEntityCallback("presence")
    def onPresence(self, entity):
        self.notifications.on_presence(entity)

    async def _sendIqAsync(self, entity):
        return await self.iq_mgr.send_iq_async(entity)

    async def executeCommand(self, command_name, params=None, options=None):
        if params is None:
            params = []
        if options is None:
            options = {}
        if command_name not in self.bot.cmdList:
            available = ", ".join(sorted(self.bot.cmdList.keys()))
            raise KeyError(
                f"Command '{command_name}' not found. Available commands: {available[:100]}..."
            )
        cmd_func = self.bot.cmdList[command_name]
        self.logger.debug(f"Executing command: {command_name} with params={params}, options={options}")
        try:
            result = await cmd_func(params, options)
            self.logger.debug(f"Command '{command_name}' result: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Command '{command_name}' failed: {e}")
            raise

    def callback(self, event=None, message=None, messageStatus=None, cmdResult=None, modeResult=None):
        self.bot.callback(event, message, messageStatus, cmdResult, modeResult)

    def setCmdResult(self, cmdId, result):
        self.bot.setCmdResult(cmdId, result)

    def setCmdError(self, cmdId, error):
        self.bot.setCmdError(cmdId, error)

    def setMode(self, mode):
        self.mode = mode

    async def gpia(self, params, options):
        self.logger.info("no adp support , so ignore it ")
        return "JUSTWAIT"

    async def safetynet(self, params, options):
        self.logger.info("no adp support , so ignore it ")
        return "JUSTWAIT"

    def genProfile(self, device_identity):
        return self.pairing.gen_profile(device_identity)

    async def download(self, params):
        return await self.media.download(params)

    def parseMediaCommonAttributes(self, msg, media_specific_attributes):
        return self.media.parse_media_common_attributes(msg, media_specific_attributes)

    async def assureContactsAndSend(self, cmdParams, options, send_func, redo_func):
        return await self.contacts.assure_contacts_and_send(cmdParams, options, send_func, redo_func)

    async def getContactList(self, cmdParams, options):
        return await self.contacts.get_contact_list(cmdParams, options)

    def getContextValue(self, ctxId, key):
        return self.contacts.get_context_value(ctxId, key)

    async def fcmMsgCallback(self, obj, data, p):
        return await self.sync.fcm_msg_callback(obj, data, p)

    async def resetSync(self, params, options):
        return await self.sync.reset_sync(params, options)

    def generateAppStateSyncKeys(self, n):
        return self.sync.generate_app_state_sync_keys(n)

    async def logoutApprove(self, cmdParams, options):
        return await self.sync.logout_approve(cmdParams, options)

    async def syncData(self, cmdParams, options):
        return await self.sync.sync_data(cmdParams, options)
