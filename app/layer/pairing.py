"""PairingManager — QR code & link code companion device registration and account sync."""

import asyncio
import logging
import random
import sys
import time
from pathlib import Path

import qrcode
from axolotl.ecc.curve import Curve
from axolotl.ecc.djbec import DjbECPrivateKey, DjbECPublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from Crypto.Random import get_random_bytes

from proto import wa_struct_pb2
from core.common import YowConstants
from core.common.tools import Jid, WATools
from core.config.v1.config import Config
from core.layers import YowLayerEvent
from core.layers.network.layer import YowNetworkLayer
from core.layers.axolotl.protocolentities.iq_key_get import GetKeysIqProtocolEntity
from core.layers.protocol_appstate.protocolentities.attributes import *
from core.layers.protocol_appstate.protocolentities.hash_state import HashState
from core.layers.protocol_appstate.protocolentities.mutation_keys import MutationKeys
from core.layers.protocol_appstate.protocolentities.patch_builder import PatchBuilder
from core.layers.protocol_historysync.protocolentities.attributes import *
from core.layers.protocol_historysync.protocolentities.history_sync import HistorySync
from core.layers.protocol_iq.protocolentities import *
from core.layers.protocol_media.protocolentities import RequestMediaConnIqProtocolEntity
from core.layers.protocol_messages.protocolentities import ProtocolMessageProtocolEntity
from core.layers.protocol_messages.protocolentities.attributes import (
    ProtocolAttributes,
    MessageMetaAttributes,
)
from core.layers.protocol_historysync.protocolentities.attributes import (
    InitialSecurityNotificationSettingSyncAttribute,
    AppStateSyncKeyShareAttribute,
)
from core.profile.profile import YowProfile
from common.utils import Utils
from conf.constants import SysVar
from app.zowbot_values import ZowBotType

logger = logging.getLogger(__name__)


class PairingManager:
    """Manages companion device pairing: QR scan, link code, device identity, and history sync."""

    def __init__(self, layer):
        """
        Args:
            layer: ZowBotLayer instance
        """
        self.layer = layer

        # Pairing state
        self.status = None  # e.g. "WAIT_PAIRINGCODE"
        self.code = None  # pairing code input
        self.companion_hello_entity = None

    # ── QR code display task ─────────────────────────────────────────────

    async def _run_qr_display(self, interval):
        """Asyncio task: display QR codes for companion device scanning."""
        try:
            while True:
                refs = self.layer.getProp("refs")
                if len(refs) > 0:
                    ref = refs.pop(0)
                    regInfo = self.layer.getProp("reg_info")
                    keypair = regInfo["keypair"]
                    identity = regInfo["identity"]
                    advSecretKey = random.randbytes(32)
                    logger.debug(
                        "{},{},{},{}".format(
                            str(ref, "utf8"),
                            Utils.b64str(keypair.public.data),
                            Utils.b64str(identity.publicKey.serialize()[1:]),
                            Utils.b64str(advSecretKey),
                        )
                    )
                    qr = qrcode.QRCode()
                    qr.border = 1
                    qr.add_data(
                        "{},{},{},{}".format(
                            str(ref, "utf8"),
                            Utils.b64str(keypair.public.data),
                            Utils.b64str(identity.publicKey.serialize()[1:]),
                            Utils.b64str(advSecretKey),
                        )
                    )
                    qr.make()
                    qr.print_ascii(out=None, tty=False, invert=False)
                    sys.stdout.flush()
                    self.layer.setProp("refs", refs)
                else:
                    await self.layer.getStack().broadcastEvent(
                        YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT)
                    )
                    return
                for i in range(0, interval):
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.debug("QR code task cancelled")

    # ── Profile generation ──────────────────────────────────────────────────

    def gen_profile(self, device_identity):
        """Create and persist a YowProfile after successful companion registration."""
        regInfo = self.layer.getProp("reg_info")
        regid = regInfo["regid"]
        keypair = regInfo["keypair"]
        jid = self.layer.getProp("jid")
        phone, a, deviceid = WATools.jidDecode(jid)
        identity = regInfo["identity"]
        cc = Utils.getMobileCC(phone)
        mccmnc = {"mcc": "000", "mnc": "000"}
        config = Config(
            cc=cc,
            mcc=mccmnc["mcc"],
            mnc=mccmnc["mnc"],
            phone=phone,
            device=int(deviceid),
            client_static_keypair=keypair,
            device_identity=Utils.b64str(device_identity.SerializeToString()),
        )
        account_dir = Path(SysVar.ACCOUNT_PATH + phone + "_" + str(deviceid))
        Utils.assureDir(account_dir)
        profile = YowProfile(
            SysVar.ACCOUNT_PATH + phone + "_" + str(deviceid), config
        )
        profile.write_config()
        db = profile.axolotl_manager

        q = (
            "UPDATE identities SET registration_id=? , public_key=?, private_key=?,"
            "device_id=? WHERE recipient_id=-1"
        )
        c = db._store.identityKeyStore.dbConn.cursor()
        pubKey = identity.publicKey.serialize()
        privKey = identity.privateKey.serialize()
        c.execute(q, (regid, pubKey, privKey, deviceid))
        signedprekey = regInfo["signedprekey"]
        db._store.storeSignedPreKey(signedprekey.getId(), signedprekey)
        db._store.removeAllPreKeys()
        db._store.identityKeyStore.dbConn.commit()
        self.layer.bot.profile = profile

    # ── Pair IQ (QR / LinkCode dispatch) ────────────────────────────────────

    async def handle_pair_iq(self, entity):
        """Handle MultiDevicePairIqProtocolEntity — dispatch QR vs LinkCode."""

        def on_success(entity, original_iq_entity):
            self.layer.logger.info("Pairing Start Success")

        def on_error(entity, original_iq):
            self.layer.logger.error(
                f"Pairing Start Fail with code {entity.code} - {entity.text} "
            )

        if self.layer.getProp("botType") == ZowBotType.TYPE_REG_COMPANION_SCANQR:
            logger.info("QRCode Pairing")
            ack = IqProtocolEntity(
                to=YowConstants.WHATSAPP_SERVER, _type="result", _id=entity.getId()
            )
            await self.layer._sendIq(ack)
            self.layer.setProp("refs", entity.refs)
            # Start QR display asyncio task
            self.layer._qrTask = asyncio.ensure_future(self._run_qr_display(20))
            return

        elif self.layer.getProp("botType") == ZowBotType.TYPE_REG_COMPANION_LINKCODE:
            logger.info("LinkCode Pairing")
            ack = IqProtocolEntity(
                to=YowConstants.WHATSAPP_SERVER, _type="result", _id=entity.getId()
            )
            await self.layer._sendIq(ack)
            linkCodePairingWrappedCompanionEphemeralPub = Utils.link_code_encrypt(
                self.layer.bot.pairLinkCode,
                self.layer.getProp("reg_info")["keypair"].public.data,
            )
            companionServerAuthKeyPub = self.layer.getProp("reg_info")[
                "keypair"
            ].public.data
            jid = self.layer.bot.pairPhoneNumber + "@s.whatsapp.net"
            entity = MultiDevicePairCompanionHelloIqProtocolEntity(
                jid,
                shouldshowPushNotification="true",
                linkCodePairingWrappedCompanionEphemeralPub=linkCodePairingWrappedCompanionEphemeralPub,
                companionServerAuthKeyPub=companionServerAuthKeyPub,
            )
            await self.layer._sendIq(entity, on_success, on_error)
            return

    # ── Pair Success IQ (sign device + gen profile) ─────────────────────────

    async def handle_pair_success_iq(self, entity):
        """Handle MultiDevicePairSuccessIqProtocolEntity — sign device, gen profile."""
        jid = entity.jid
        print(jid, flush=True)  # signal login success to dashboard SSE stream
        self.layer.setProp("refs", None)
        self.layer.setProp("jid", jid)
        self.layer.setProp("botType", ZowBotType.TYPE_RUN_SINGLETON)
        p1 = wa_struct_pb2.ADVSignedDeviceIdentityHMAC()
        p1.ParseFromString(entity.device_identity)
        p2 = wa_struct_pb2.ADVSignedDeviceIdentity()
        p2.ParseFromString(p1.details)
        p3 = wa_struct_pb2.ADVDeviceIdentity()
        p3.ParseFromString(p2.details)
        identity = self.layer.getProp("reg_info")["identity"]
        buffer = (
            b"\x06\x01"
            + p2.details
            + identity.publicKey.serialize()[1:]
            + p2.account_signature_key
        )
        devicesign = Curve.calculateSignature(identity.privateKey, buffer)
        p4 = wa_struct_pb2.ADVSignedDeviceIdentity()
        p4.account_signature_key = p2.account_signature_key
        p4.account_signature = p2.account_signature
        p4.details = p2.details
        p4.device_signature = devicesign
        signEntity = MultiDevicePairSignIqProtocolEntity(
            entity.getId(), p3.key_index, p4.SerializeToString()
        )
        await self.layer._sendIq(signEntity)
        self.gen_profile(p4)
        return

    # ── LinkCode notification dispatch ──────────────────────────────────────

    async def handle_linkcode_notification(self, entity):
        """Handle LinkCodeCompanionRegNotificationProtocolEntity stages."""
        self.layer.logger.info(
            "Notification: Received a LinkCodeCompanionReg, stage={}".format(entity.stage)
        )

        if entity.stage == "primary_hello":
            await self._handle_linkcode_primary_hello(entity)
            return

        if entity.stage == "companion_hello":
            await self._handle_linkcode_companion_hello(entity)
            return

        if entity.stage == "companion_finish":
            await self._handle_linkcode_companion_finish(entity)
            return

    async def _handle_linkcode_primary_hello(self, entity):
        """LinkCode stage: primary_hello — decrypt link code and send companion finish."""
        linkCode = self.layer.bot.pairLinkCode
        primaryEphemeralPub = Utils.link_code_decrypt(
            linkCode, entity.linkCodePairingWrappedPrimaryEphemeralPub
        )
        shareEphemeralSecret = Curve.calculateAgreement(
            DjbECPublicKey(primaryEphemeralPub),
            DjbECPrivateKey(
                self.layer.getProp("reg_info")["keypair"].private.data
            ),
        )
        linkCodePairingEphemeralRootSecret = get_random_bytes(32)
        encryptPayload = (
            self.layer.getProp("reg_info")["identity"].publicKey.serialize()[1:]
            + entity.primaryIdentityPublic
            + linkCodePairingEphemeralRootSecret
        )
        companionFinishKdfSalt = get_random_bytes(32)
        linkCodePairingKeyBundleEncryptionKey = Utils.extract_and_expand(
            shareEphemeralSecret,
            b"link_code_pairing_key_bundle_encryption_key",
            32,
            companionFinishKdfSalt,
        )
        companionFinishIV = get_random_bytes(12)
        cipher = AESGCM(linkCodePairingKeyBundleEncryptionKey)
        encrypted = cipher.encrypt(companionFinishIV, encryptPayload, b"")
        encryptedPayload = companionFinishKdfSalt + companionFinishIV + encrypted
        identitySharedKey = Curve.calculateAgreement(
            DjbECPublicKey(entity.primaryIdentityPublic),
            DjbECPrivateKey(
                self.layer.getProp("reg_info")["identity"].privateKey.serialize()
            ),
        )
        linkingSecretKeyMaterial = (
            shareEphemeralSecret
            + identitySharedKey
            + linkCodePairingEphemeralRootSecret
        )
        advSecretPublicKey = Utils.extract_and_expand(
            linkingSecretKeyMaterial, b"adv_secret", 32
        )
        finish_entity = MultiDevicePairCompanionFinishIqProtocolEntity(
            self.layer.bot.pairPhoneNumber + "@s.whatsapp.net",
            encryptedPayload,
            self.layer.getProp("reg_info")["identity"].publicKey.serialize()[1:],
            entity.linkCodePairingRef,
        )
        await self.layer.toLower(finish_entity)

    async def _handle_linkcode_companion_hello(self, entity):
        """LinkCode stage: companion_hello — wait for pairing code input."""
        logger.info("ENTERING WAITING CODE STATUS")
        self.status = "WAIT_PAIRINGCODE"
        self.companion_hello_entity = entity

        logger.debug("bot_type: {}".format(self.layer.bot.bot_type))

        if self.layer.bot.bot_type == ZowBotType.TYPE_RUN_TEMP:
            # Auto-input pairing code for temporary mode
            await self.layer.executeCommand("md.inputcode", ["AAAAAA"])

    async def _handle_linkcode_companion_finish(self, entity):
        """LinkCode stage: companion_finish — key exchange and pair device."""
        if self.layer.getProp("keypair") is None:
            return

        ref = entity.linkCodePairingRef
        companionEphemerPub = self.layer.getProp("companionEphemerPub")
        companionIdentityPublic = entity.companionIdentityPublic
        companionServerAuthKeyPub = self.layer.getProp("companionAuthKeyPub")
        companionFinishKdfSalt = entity.linkCodePairingWrappedKeyBundle[:32]
        companionFinishIV = entity.linkCodePairingWrappedKeyBundle[32:44]
        linkCodePairingEncryptedKeyBundle = entity.linkCodePairingWrappedKeyBundle[44:]

        shareEphemeralSecret = Curve.calculateAgreement(
            DjbECPublicKey(companionEphemerPub),
            DjbECPrivateKey(self.layer.getProp("keypair").private.data),
        )
        linkCodePairingKeyBundleEncryptionKey = Utils.extract_and_expand(
            shareEphemeralSecret,
            b"link_code_pairing_key_bundle_encryption_key",
            32,
            companionFinishKdfSalt,
        )
        cipher = AESGCM(linkCodePairingKeyBundleEncryptionKey)
        linkCodePairingKeyBundle = cipher.decrypt(
            companionFinishIV, linkCodePairingEncryptedKeyBundle, b""
        )
        identitySharedKey = Curve.calculateAgreement(
            DjbECPublicKey(companionIdentityPublic),
            DjbECPrivateKey(self.layer.db.identity.privateKey.serialize()),
        )
        linkCodePairingEphemeralRootSecret = linkCodePairingKeyBundle[-32:]
        linkingSecretKeyMaterial = (
            shareEphemeralSecret
            + identitySharedKey
            + linkCodePairingEphemeralRootSecret
        )
        advSecretPublicKey = Utils.extract_and_expand(
            linkingSecretKeyMaterial, b"adv_secret", 32
        )
        await self.layer.resetSync([], {})
        profile = self.layer.getProp("profile")
        ref, pubKey, deviceIdentity, keyIndexList = Utils.generateMultiDeviceParams(
            ref,
            companionServerAuthKeyPub,
            companionIdentityPublic,
            advSecretPublicKey,
            profile,
        )
        pair_entity = MultiDevicePairDeviceIqProtocolEntity(
            ref=ref,
            pubKey=pubKey,
            deviceIdentity=deviceIdentity,
            keyIndexList=keyIndexList,
        )

        def on_pair_device_success(entity, original_iq_entity):
            companionJid = entity.deviceJid
            deviceIdx = int(companionJid.split("@")[0].split(":")[1])
            profile.config.add_device_to_list(deviceIdx)
            profile.write_config(profile.config)
            self.layer.getStack().setProp("pair-companion-jid", companionJid)

        def on_pair_device_error(entity, original_iq):
            logger.error("pair device error")
            self.layer.bot.quit()

        await self.layer._sendIq(
            pair_entity, on_pair_device_success, on_pair_device_error
        )

    # ── Account Sync Notification (companion history sync chain) ────────────

    async def handle_account_sync_notification(self, entity):
        """Handle AccountSyncNotification — initiate companion history sync chain."""
        self.layer.logger.info("Notification: Received a AccountSync Notification")
        companionJid = self.layer.getStack().getProp("pair-companion-jid")
        if companionJid is None:
            return

        layer = self.layer  # capture for closures

        get_keys_entity = GetKeysIqProtocolEntity(
            [companionJid], _id=layer.bot.idType
        )

        async def on_get_encrypt_success(entity, original_iq_entity):
            # Send initial security notification
            sec_entity = ProtocolMessageProtocolEntity(
                protocol_attr=ProtocolAttributes(
                    type=ProtocolAttributes.TYPE_INITIAL_SECURITY_NOTIFICATION_SETTING_SYNC,
                    initial_security_notification_setting_sync=InitialSecurityNotificationSettingSyncAttribute(
                        security_notification_enabled=True
                    ),
                ),
                message_meta_attributes=MessageMetaAttributes(
                    recipient=companionJid, category="peer"
                ),
            )
            await layer.toLower(sec_entity)

            # Generate and share app state sync keys
            sync_keys = layer.generateAppStateSyncKeys(10)
            if layer.db:
                layer.db._store.addAppStateKeys(sync_keys)

            key_share_entity = ProtocolMessageProtocolEntity(
                protocol_attr=ProtocolAttributes(
                    type=ProtocolAttributes.TYPE_APP_STATE_SYNC_KEY_SHARE,
                    app_state_sync_key_share=AppStateSyncKeyShareAttribute(
                        keys=sync_keys
                    ),
                ),
                message_meta_attributes=MessageMetaAttributes(
                    recipient=companionJid, category="peer"
                ),
            )
            await layer.toLower(key_share_entity)
            await asyncio.sleep(3)

            async def on_get_conn_success(conn_entity, original_iq_entity):
                hs = HistorySync(conn_entity, companionJid)

                et = hs.createNonBlockingDataMessage()
                await layer.toLower(et)
                et = hs.createInitialStatusV3Message()
                await layer.toLower(et)
                et = hs.createPushNameMessage()
                await layer.toLower(et)
                et = hs.createInitialBootstrapMessage(
                    conversations=[ConversationAttribute(id="TEST")]
                )
                await layer.toLower(et)
                et = hs.createRecentMessage()
                await layer.toLower(et)

                et = TrustContactIqProtocolEntity(
                    Jid.normalize(layer.bot.botId), int(time.time())
                )
                await layer.toLower(et)

                # ── App State Sync ──────────────────────────────────
                if not layer.db:
                    return

                key = layer.db._store.getOneAppStateKey()
                mutationKeys = MutationKeys.createFromKey(key.key_data.key_data)

                localeSetting = SyncActionDataAttribute.createFromSyncActionValue(
                    SyncActionValueAttribute(
                        localeSetting=SyncActionLocaleSettingAttribute(locale="zh_CN")
                    )
                )
                pushNameSetting = SyncActionDataAttribute.createFromSyncActionValue(
                    SyncActionValueAttribute(
                        pushNameSetting=SyncActionPushnameSettingAttribute(
                            name="enx test"
                        )
                    )
                )

                state = HashState("critical_block", 0)
                state, syncdPatch1 = (
                    PatchBuilder(state, mutationKeys, key)
                    .addMutation(localeSetting)
                    .addMutation(pushNameSetting)
                    .finish()
                )

                name1 = SyncActionDataAttribute.createFromSyncActionValue(
                    SyncActionValueAttribute(
                        contactAction=SyncActionContactActionAttribute(
                            fullName="test user",
                            firstName="test",
                            lidJid="8618502060000@s.whatsapp.net",
                        )
                    ).setArgs(["8618502060000@s.whatsapp.net"])
                )

                state2 = HashState("critical_unblock_low", 0)
                state2, syncdPatch2 = (
                    PatchBuilder(state2, mutationKeys, key)
                    .addMutation(name1)
                    .finish()
                )

                app_sync_entity = AppSyncStateIqProtocolEntity(
                    patches={
                        "critical_unblock_low": syncdPatch2.encode(),
                        "critical_block": syncdPatch1.encode(),
                    }
                )
                await layer.toLower(app_sync_entity)

            def on_get_conn_error(entity, original_iq_entity):
                layer.logger.error("get conn error")

            conniq = RequestMediaConnIqProtocolEntity()
            await layer._sendIq(conniq, on_get_conn_success, on_get_conn_error)

        def on_get_encrypt_error(entity, on_get_encrypt_error):
            layer.logger.error("error get encrypt")

        await layer._sendIq(
            get_keys_entity, on_get_encrypt_success, on_get_encrypt_error
        )
