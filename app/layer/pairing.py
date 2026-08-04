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

from core.layers.axolotl.props import PROP_IDENTITY_AUTOTRUST
from proto import wa_struct_pb2
from core.common import YowConstants
from core.common.tools import Jid, WATools
from core.config.v1.config import Config
from core.layers import YowLayerEvent, IqErrorException
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
        self.wa_fbid = None  # Facebook ID from CanonicalEntCredentials
        self.canonical_password = None  # Stored password from WWWCreateUser

        # Load canonical credentials from profile config if available
        self._load_fbinfo_from_config()

    def _load_fbinfo_from_config(self):
        """Load canonical credentials from profile config on startup."""
        try:
            profile = self.layer.getStack().getProp("profile") if self.layer.getStack() else None
            if profile and profile.config:
                cfg = profile.config
                if cfg.fbibnfo :
                    self.wa_fbid = str(cfg.fbibnfo["fb_id"])
                    self.layer._fbid = self.wa_fbid
                    logger.info(f"Loaded canonical credentials from config (fb_id={self.wa_fbid})")
        except Exception as e:
            logger.debug(f"No canonical credentials in config: {e}")

    # ── Ensure Canonical Ent Credentials ───────────────────────────────────

    async def ensure_canonical_credentials(self):
        """Ensure we have canonical fb_id. Cache in memory/config, or fetch via WWWTriggerAcountRecovery."""
        # Step 1: Check in-memory cache
        if self.wa_fbid:
            self.layer.logger.info(f"Using cached canonical fb_id={self.wa_fbid}")
            return {"fb_id": self.wa_fbid}

        # Step 2: Check profile config
        profile = self.layer.getStack().getProp("profile")
        if profile and profile.config and profile.config.fbinfo:
            self.wa_fbid = str(profile.config.fbinfo["fb_id"])
            self.layer._fbid = self.wa_fbid
            self.layer.logger.info(f"Loaded canonical fb_id from config ({self.wa_fbid})")
            return {"fb_id": self.wa_fbid}

        # Step 3: Call WWWTriggerAcountRecovery
        from app.layer.canonical_credentials import trigger_account_recovery

        self.layer.logger.info("Requesting canonical fbid via WWWTriggerAcountRecovery...")
        credentials = await trigger_account_recovery(self.layer)
        if credentials:
            self.wa_fbid = credentials["fb_id"]
            self.layer._fbid = self.wa_fbid
            self.layer.logger.info(f"Canonical fbid obtained: {self.wa_fbid}")
            if profile and profile.config:
                profile.config.fbinfo["fb_id"] = self.wa_fbid
                profile.write_config()
            return credentials

        self.layer.logger.error("Failed to obtain canonical fbid")
        return None

    async def _send_deferred_nonce_response(self, companion_jid, nonce, fbid):
        """Send PeerDataOperation nonce response after session is established.

        Waits for the axolotl session to be created (by polling session_exists),
        then sends the PeerDataOperation response with nonce + waFbid.
        """
        import asyncio

        # Wait for session to be established (max 10 seconds)
        for i in range(20):
            try:
                # Check if session exists by looking at the axolotl store
                phone, _, device = WATools.jidDecode(companion_jid)
                username = f"{phone}:{device}"
                if self.layer.db and self.layer.db._store.sessionStore:
                    if self.layer.db._store.sessionStore.loadSession(username, 1):
                        break
            except Exception:
                pass
            await asyncio.sleep(0.5)

        try:
            from proto.e2e_pb2 import Message as ProtoMessage
            from core.layers.protocol_messages.protocolentities import (
                ProtocolMessageProtocolEntity,
            )
            from core.layers.protocol_messages.protocolentities.attributes import (
                ProtocolAttributes, MessageMetaAttributes,
            )

            self.layer.logger.info(
                f"Sending PeerDataOperation nonce response to {companion_jid} "
                f"(session established)"
            )

            resp_msg = ProtoMessage()
            resp_msg.protocol_message.type = \
                ProtoMessage.ProtocolMessage.PEER_DATA_OPERATION_REQUEST_RESPONSE_MESSAGE
            pr = resp_msg.protocol_message.peer_data_operation_request_response_message
            result = pr.peerDataOperationResult.add()
            resp = result.companionCanonicalUserNonceFetchRequestResponse
            resp.nonce = nonce
            if fbid:
                resp.waFbid = fbid
            resp.forceRefresh = False

            resp_entity = ProtocolMessageProtocolEntity(
                protocol_attr=ProtocolAttributes(
                    type=ProtocolAttributes.TYPE_PEER_DATA_OPERATION_REQUEST_RESPONSE_MESSAGE,
                    peer_data_operation_request_response_message=pr,
                ),
                message_meta_attributes=MessageMetaAttributes(
                    recipient=companion_jid, category="peer"
                ),
            )
            resp_entity.raw = resp_msg.SerializeToString()
            await self.layer.toLower(resp_entity)
            self.layer.logger.info("PeerDataOperation nonce response sent to companion")

            # Clear stored values
            self.layer.getStack().setProp("pair-companion-nonce", None)
            self.layer.getStack().setProp("pair-companion-fbid", None)
        except Exception as e:
            self.layer.logger.warning(f"Failed to send deferred PeerDataOp response: {e}")

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

        if self.layer.getProp("botType") == ZowBotType.TYPE_REG_COMPANION_SCANQR:
            logger.info("QRCode Pairing")
            ack = IqProtocolEntity(
                to=YowConstants.WHATSAPP_SERVER, _type="result", _id=entity.getId()
            )
            await self.layer.sendIqFireAndForget(ack)
            self.layer.setProp("refs", entity.refs)
            # Start QR display asyncio task
            self.layer._qrTask = asyncio.ensure_future(self._run_qr_display(20))
            return

        elif self.layer.getProp("botType") == ZowBotType.TYPE_REG_COMPANION_LINKCODE:
            logger.info("LinkCode Pairing")
            ack = IqProtocolEntity(
                to=YowConstants.WHATSAPP_SERVER, _type="result", _id=entity.getId()
            )
            await self.layer.sendIqFireAndForget(ack)
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
            try:
                await self.layer.sendIqAsync(entity)
            except IqErrorException as e:
                self.layer.logger.error(
                    f"Pairing Start Fail with code {e.error_node.code} - {e.error_node.text} "
                )
            else:
                self.layer.logger.info("Pairing Start Success")
            return

    # ── Pair Success IQ (sign device + gen profile) ─────────────────────────

    async def handle_pair_success_iq(self, entity):
        """Handle MultiDevicePairSuccessIqProtocolEntity — sign device, gen profile."""
        jid = entity.jid
        print(jid, flush=True)  # signal login success to dashboard SSE stream
        self.layer.setProp("refs", None)
        self.layer.setProp("jid", jid)
        self.layer.setProp("botType", ZowBotType.TYPE_RUN_SINGLETON)
        # Unwrap the device identity chain:
        #   entity.device_identity (bytes) -> ADVSignedDeviceIdentityHMAC
        #       -> details -> ADVSignedDeviceIdentity
        #       -> details -> ADVDeviceIdentity
        device_identity_hmac = wa_struct_pb2.ADVSignedDeviceIdentityHMAC()
        device_identity_hmac.ParseFromString(entity.device_identity)

        signed_device_identity = wa_struct_pb2.ADVSignedDeviceIdentity()
        signed_device_identity.ParseFromString(device_identity_hmac.details)

        device_identity_meta = wa_struct_pb2.ADVDeviceIdentity()
        device_identity_meta.ParseFromString(signed_device_identity.details)

        self.layer.logger.info(
            f"pair-success device-identity: raw_id={device_identity_meta.raw_id} "
            f"ts={device_identity_meta.timestamp} "
            f"key_index={device_identity_meta.key_index} "
            f"account_type={device_identity_meta.account_type} "
            f"device_type={device_identity_meta.device_type} "
            f"hmac_account_type={device_identity_hmac.account_type} "
            f"account_sig_len={len(signed_device_identity.account_signature)} "
            f"device_sig_len={len(signed_device_identity.device_signature)}"
        )

        reg_identity = self.layer.getProp("reg_info")["identity"]
        # Device Signature (WhatsApp docs):
        #   Dsignature = SIGN(Icompanion, DEVICE_SIGNATURE_PREFIX || Lmetadata || Icompanion || Iprimary)
        #   DEVICE_SIGNATURE_PREFIX = 0x0606 if Cloud API (HOSTED), else 0x0601
        is_hosted = (
            device_identity_hmac.account_type == 1
            or device_identity_meta.account_type == 1
        )
        signature_prefix = b"\x06\x06" if is_hosted else b"\x06\x01"
        signature_buffer = (
            signature_prefix
            + signed_device_identity.details
            + reg_identity.publicKey.serialize()[1:]
            + signed_device_identity.account_signature_key
        )
        device_signature = Curve.calculateSignature(
            reg_identity.privateKey, signature_buffer
        )

        companion_signed_identity = wa_struct_pb2.ADVSignedDeviceIdentity()
        companion_signed_identity.account_signature_key = (
            signed_device_identity.account_signature_key
        )
        companion_signed_identity.account_signature = signed_device_identity.account_signature
        companion_signed_identity.details = signed_device_identity.details
        companion_signed_identity.device_signature = device_signature

        sign_entity = MultiDevicePairSignIqProtocolEntity(
            entity.getId(),
            device_identity_meta.key_index,
            companion_signed_identity.SerializeToString(),
        )
        await self.layer.sendIqFireAndForget(sign_entity)
        self.gen_profile(companion_signed_identity)
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
        params_v2 = Utils.generateMultiDeviceParams(
            ref=ref,
            companion_noise_pub=companionServerAuthKeyPub,
            companion_identity_pub=companionIdentityPublic,
            adv_secret=advSecretPublicKey,
            account_type=0,
            profile=profile)
        
        pair_entity = MultiDevicePairDeviceIqProtocolEntity(
            ref=ref,
            pubKey=params_v2["noise_pub"],
            deviceIdentity=params_v2["device_identity"],
            keyIndexList=params_v2["key_index_list"],
            keyIndexTs=params_v2["key_index_ts"]
        )
        
        try:
            result_dict = await self.layer.sendIqAsync(pair_entity)
        except IqErrorException as e:
            logger.error("pair device error")
            self.layer.bot.quit()
            return

        result_entity = result_dict["result"]
        companionJid = result_entity.deviceJid
        deviceIdx = int(companionJid.split("@")[0].split(":")[1])
        profile.config.add_device_to_list(deviceIdx)
        profile.write_config(profile.config)
        self.layer.getStack().setProp("pair-companion-jid", companionJid)

    # ── Account Sync Notification (companion history sync chain) ────────────

    async def handle_account_sync_notification(self, entity):
        """Handle AccountSyncNotification — initiate companion history sync chain."""
        self.layer.logger.info("Notification: Received a AccountSync Notification")
        
        companionJid = getattr(entity, 'companion_jid', None)
        if companionJid is None:
            self.layer.logger.warning("handle_account_sync: no companion LID JID found in notification")
            return
                
        self.layer.logger.info(f"handle_account_sync: companionJid={companionJid}")
        self.layer.getStack().setProp("pair-companion-jid", companionJid)

        layer = self.layer  

        get_keys_entity = GetKeysIqProtocolEntity(
            [companionJid], _id=layer.bot.idType
        )

        async def on_get_encrypt_success(keys_entity):

            resultJids = keys_entity.getJids()                   
            for jid in resultJids:     
                preKeyBundle = keys_entity.getPreKeyBundleFor(jid)
                try:               
                    logger.info("CREATE SESSION SUCCESS")
                    self.manager.create_session(jid, preKeyBundle,
                                                autotrust=self.getProp(PROP_IDENTITY_AUTOTRUST, False))                    
                except Exception as e:
                    logger.warning("get key exception")            

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
            sync_keys = layer.generateAppStateSyncKeys(1)
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

            pdorm_nonce = layer.getStack().getProp("pair-companion-nonce")
            pdorm_fbid = layer.getStack().getProp("pair-companion-fbid")
            if pdorm_nonce:
                pdorm_entity = ProtocolMessageProtocolEntity(
                    protocol_attr=ProtocolAttributes(
                        type = ProtocolAttributes.TYPE_PEER_DATA_OPERATION_REQUEST_RESPONSE_MESSAGE,
                        peer_data_operation_request_response_message=PeerDataOperationRequestResponseMessageAttribute(
                            nonce=pdorm_nonce,
                            waFbid=pdorm_fbid,
                            forceRefresh=False
                        )
                    ),
                    message_meta_attributes=MessageMetaAttributes(
                        recipient=companionJid, category="peer"
                    ),                
                )
                await layer.toLower(pdorm_entity)
            else:
                logger.warning("handle_account_sync: pair-companion-nonce is None, skipping PDORM")

            await asyncio.sleep(3)

            async def on_get_conn_success(conn_entity):
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
                            lidJid="158455033810989@lid",
                        )
                    ).setArgs(["158455033810989@lid"])
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

            conniq = RequestMediaConnIqProtocolEntity()
            try:
                conn_result = await layer.sendIqAsync(conniq)
            except Exception as e:
                layer.logger.error("get conn error: %s", e)
            else:
                await on_get_conn_success(conn_result["result"])

        await asyncio.sleep(3)
        try:
            keys_result = await layer.sendIqAsync(get_keys_entity)
        except Exception as e:
            layer.logger.error("error get encrypt: %s", e)
        else:
            await on_get_encrypt_success(keys_result["result"])
