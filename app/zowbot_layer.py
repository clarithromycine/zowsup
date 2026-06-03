# ============================================================================
# Standard Library Imports
# ============================================================================
import asyncio
import base64
import configparser
import io
import logging
import mimetypes
import os
import random
import sys
import threading
import time
from pathlib import Path
from typing import Any

sys.path.append(os.getcwd())

# ============================================================================
# Third-Party Imports
# ============================================================================
import qrcode
import requests
from axolotl.ecc.curve import Curve
from axolotl.ecc.djbec import DjbECPrivateKey, DjbECPublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from Crypto.Random import get_random_bytes

# ============================================================================
# Protocol Buffer Imports
# ============================================================================
from proto import wa_struct_pb2
from proto import zowsup_pb2

# ============================================================================
# Local Imports - Core
# ============================================================================
from core.common import YowConstants
from core.common.tools import Jid, WATools
from core.config.v1.config import Config
from core.layers import EventCallback, YowLayerEvent
from core.layers.axolotl.protocolentities import *
from core.layers.axolotl.protocolentities.iq_key_get import GetKeysIqProtocolEntity
from core.layers.axolotl.props import PROP_IDENTITY_AUTOTRUST
from core.layers.interface import YowInterfaceLayer, ProtocolEntityCallback
from core.layers.network.layer import YowNetworkLayer
from core.layers.protocol_appstate.protocolentities.attributes import *
from core.layers.protocol_appstate.protocolentities.hash_state import HashState
from core.layers.protocol_appstate.protocolentities.mutation_keys import MutationKeys
from core.layers.protocol_appstate.protocolentities.patch_builder import PatchBuilder
from core.layers.protocol_chatstate.protocolentities import *
from core.layers.protocol_contacts.protocolentities import *
from core.layers.protocol_groups.protocolentities import *
from core.layers.protocol_historysync.protocolentities.attributes import *
from core.layers.protocol_historysync.protocolentities.history_sync import HistorySync
from core.layers.protocol_ib.protocolentities import *
from core.layers.protocol_iq.protocolentities import *
from core.layers.protocol_media.mediacipher import MediaCipher
from core.layers.protocol_media.protocolentities import *
from core.layers.protocol_messages.protocolentities import *
from core.layers.protocol_messages.protocolentities.attributes import *
from core.layers.protocol_notifications.protocolentities import *
from core.layers.protocol_presence.protocolentities import *
from core.layers.protocol_presence.protocolentities.presence import PresenceProtocolEntity
from core.layers.protocol_privacy.protocolentities import *
from core.layers.protocol_profiles.protocolentities import *
from core.profile.profile import YowProfile

# ============================================================================
# Local Imports - Configuration & Utilities
# ============================================================================
from common.utils import Utils
from conf.constants import SysVar
from .zowbot_values import ZowBotStatus, ZowBotType

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

async def _qr_code_task(layer, interval):
    """Asyncio task replacing YowQrCodeThread."""
    try:
        while True:
            refs = layer.getProp("refs")
            if len(refs) > 0:
                ref = refs.pop(0)
                regInfo = layer.getProp("reg_info")
                keypair = regInfo["keypair"]
                identity = regInfo["identity"]
                advSecretKey = random.randbytes(32)
                logger.debug("{},{},{},{}".format(
                    str(ref, "utf8"),
                    str(base64.b64encode(keypair.public.data), "utf8"),
                    str(base64.b64encode(identity.publicKey.serialize()[1:]), "utf8"),
                    str(base64.b64encode(advSecretKey), "utf8")
                ))
                qr = qrcode.QRCode()
                qr.border = 1
                qr.add_data("{},{},{},{}".format(
                    str(ref, "utf8"),
                    str(base64.b64encode(keypair.public.data), "utf8"),
                    str(base64.b64encode(identity.publicKey.serialize()[1:]), "utf8"),
                    str(base64.b64encode(advSecretKey), "utf8")
                ))
                qr.make()
                qr.print_ascii(out=None, tty=False, invert=False)
                sys.stdout.flush()
                layer.setProp("refs", refs)
            else:
                await layer.getStack().broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT))
                return
            for i in range(0, interval):
                await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.debug("QR code task cancelled")



class ZowBotLayer(YowInterfaceLayer):

    PROP_MESSAGES = "org.openwhatsapp.zowsup.prop.sendclient.queue"
    PROP_WAAPI  = "org.openwhatsapp.zowsup.prop.sendclient.waapi"  

    def __init__(self,bot):
        super().__init__()
        self.ackQueue = []        
        self.isConnected = False  
        self.bot = bot      
        self.detect40x = False     
        self.detect503 = False     

        self.db = None
        
        self.mode = None        
        self.logger = logging.getLogger(self.bot.botId if self.bot.botId is not None else "unknown")
        self.msgMap = {}    
        self.loginEvent = threading.Event()        
        self.cmdEventMap = {}         
        self.pingCount = 0             
        self.ctxMap = {}
        self._qrTask = None
        self._avatarTask = None
        self.loginFailCount = 0
        self.pairingStatus = None
        


    async def _sendIqAsync(self, entity):
        """
        Send an IQ entity asynchronously and return a Future with the result.
        Returns: dict with "result" (success) or "error" (failure) key.
        Raises: asyncio.TimeoutError if no response within 30s (can be caught by caller).
        """
        loop = self.getStack().getLoop()
        future = loop.create_future() if loop else asyncio.Future()        
        async def on_success(entity_result, original_iq):
            """Wrap success callback to set future result."""
            if not future.done():
                future.set_result({"result": entity_result, "original_iq": original_iq})
        
        async def on_error(entity_error, original_iq):
            """Wrap error callback to set future exception."""
            if not future.done():
                future.set_exception(Exception(f"IQ Error: {entity_error}"))
        
        # Send the IQ with wrapped callbacks
        await super()._sendIq(entity, on_success, on_error)
        
        # Wait for response with timeout
        try:
            result = await asyncio.wait_for(future, timeout=30)
            return result
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(f"IQ response timeout for entity {entity.getId()}")
    
    async def executeCommand(self, command_name, params=None, options=None):
        """
        Execute a registered command from bot.cmdList asynchronously.
        
        This is a generic interface to call any command registered in zowbot_cmd.
        Useful for executing commands from protocol callbacks (e.g., onSuccess).
        
        Args:
            command_name (str): The command name (e.g., "account.set2fa", "account.setemail")
            params (list): Command parameters. Defaults to empty list.
            options (dict): Command options. Defaults to empty dict.
        
        Returns:
            The result from the command execution (typically a dict with success/error info).
        
        Raises:
            KeyError: If command_name is not registered in bot.cmdList.
            Exception: Any exception raised by the command execution.
        
        Example:
            await self.executeCommand("account.set2fa", ["code_123", "email@example.com"])
            await self.executeCommand("account.setemail", [""])
            await self.executeCommand("account.setname")
        """
        if params is None:
            params = []
        if options is None:
            options = {}
        
        # Validate that the command exists
        if command_name not in self.bot.cmdList:
            available = ", ".join(sorted(self.bot.cmdList.keys()))
            raise KeyError(f"Command '{command_name}' not found. Available commands: {available[:100]}...")
        
        # Get and execute the command
        cmd_func = self.bot.cmdList[command_name]
        self.logger.debug(f"Executing command: {command_name} with params={params}, options={options}")
        
        try:
            result = await cmd_func(params, options)
            self.logger.debug(f"Command '{command_name}' result: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Command '{command_name}' failed: {e}")
            raise
                        


    def genProfile(self,device_identity):
        regInfo = self.getProp("reg_info")
        regid = regInfo["regid"]
        keypair = regInfo["keypair"]
        jid = self.getProp("jid")
        phone,a,deviceid = WATools.jidDecode(jid)
        identity = regInfo["identity"]
        cc = Utils.getMobileCC(phone)        
        mccmnc = {
            "mcc":"000",
            "mnc":"000"
        }                    
        config = Config(        
            cc=cc,
            mcc=mccmnc["mcc"],
            mnc=mccmnc["mnc"],
            phone=phone,
            device=int(deviceid),           
            client_static_keypair=keypair,
            device_identity=str(base64.b64encode(device_identity.SerializeToString()),'UTF-8')
        )
        account_dir = Path(SysVar.ACCOUNT_PATH+phone+"_"+str(deviceid))
        Utils.assureDir(account_dir)        
        profile = YowProfile(SysVar.ACCOUNT_PATH+phone+"_"+str(deviceid), config)        
        profile.write_config()        
        db = profile.axolotl_manager

        q = "UPDATE identities SET registration_id=? , public_key=? , private_key=?,device_id=? WHERE recipient_id=-1"
        c = db._store.identityKeyStore.dbConn.cursor()
        pubKey = identity.publicKey.serialize()
        privKey = identity.privateKey.serialize()
        c.execute(q, (regid,                            
                    pubKey,
                    privKey,
                    deviceid))
        signedprekey = regInfo["signedprekey"]
        db._store.storeSignedPreKey(signedprekey.getId(), signedprekey)
        db._store.removeAllPreKeys()
        db._store.identityKeyStore.dbConn.commit()        
        self.bot.profile = profile

    @EventCallback(YowNetworkLayer.EVENT_STATE_DISCONNECTED)
    async def onDisconnected(self, yowLayerEvent):      
                                            
        if self.getProp("jid") is not None:           
            if self._qrTask:
                self._qrTask.cancel()
            waNum,a,deviceid = WATools.jidDecode(self.getProp("jid"))
            self.logger.info("Companion device register success(%s_%d)" % (waNum,deviceid))        
            self.setProp("jid",None)
            await asyncio.sleep(5)                                       
            self.getStack().setProfile(SysVar.ACCOUNT_PATH+waNum+"_"+str(deviceid))                       
            await self.getStack().broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECT))
            return        
        if self.getProp("refs") is not None and len(self.getProp("refs"))==0:            
            await asyncio.sleep(5)
            await self.getStack().broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECT))
            return
                
        if self.isConnected:     
            self.callback(event={
                "event":zowsup_pb2.BotEvent.Event.LOGOUT            
            })          

        self.isConnected = False

        if (not self.detect40x)  and (not self.getProp("USER_REQUEST_QUIT")) and self.loginFailCount<3 and (not self.bot.quitIfConflict):      
            self.bot.wa_old = None               
            self.loginEvent.clear()
            await asyncio.sleep(1)    
            await self.getStack().broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECT))  
                    
        else:                                                      
            if not self.getProp("HC_MODE") :
                self.bot.status = ZowBotStatus.STATUS_STOPPED              
                self.callback(event={
                    "event":zowsup_pb2.BotEvent.Event.QUIT
                })          
                if self.db:
                    self.db._store.dbConn.close()                       
                self.setProp("QUITTED",True)
            else:
                #HC模式休息1秒就好，啥都不用做                        
                self.setProp("THREADQUIT",True)
                await asyncio.sleep(1)                    

    @ProtocolEntityCallback("ib")
    async def onIb(self,entity):

        if isinstance(entity,GpiaRequestIbProtocolEntity):
            self.logger.info("Ib-gpia-request: %s" % entity.nonce)
            await self.gpia([entity.nonce],{})
        
        if isinstance(entity,SafetynetRequestIbProtocolEntity):
            self.logger.info("Ib-safetynet-request: %s" % entity.nonce)
            await self.safetynet([entity.nonce],{})


    async def gpia(self,params,options):
        self.logger.info("no adp support , so ignore it ")
        return "JUSTWAIT"


    async def safetynet(self,params,options):
        self.logger.info("no adp support , so ignore it ")
        return "JUSTWAIT"    
    
    @ProtocolEntityCallback("notification")
    async def onNotification(self,entity):        

        if isinstance(entity,MexUpdateNotificationProtocolEntity):            
            self.logger.info("Notification: Received a MexUpdate Notification: %s" % entity.jsonObj)            
            return
        
        if isinstance(entity,ServerPushConfigNotificationProtocolEntity):
            self.logger.info("Notification: Received a ServerPushConfig Notification")      
            await self.executeCommand("misc.regfcm", [],{})                         
            return
        
        if isinstance(entity,ServerSyncNotificationProtocolEntity):
            collectionNames = [] 
            if entity.collections is not None:
                for  item in entity.collections:
                    collectionNames.append(item["name"])
            self.logger.info("Notification: Received a ServerSync Notification, collections=%s" % ",".join(collectionNames))
            try:
                await self.syncData([','.join(collectionNames)] ,{})
            except Exception as e:
                self.logger.warning("syncData failed, continuing: %s", e)
            
        if isinstance(entity,AccountSyncNotificationProtocolEntity):
            self.logger.info("Notification: Received a AccountSync Notification")            
            companionJid = self.getStack().getProp("pair-companion-jid")
            if companionJid is None :
                return
            entity = GetKeysIqProtocolEntity([companionJid],_id=self.bot.idType)        
            async def on_get_encrypt_success(entity, original_iq_entity):

                entity = ProtocolMessageProtocolEntity(protocol_attr=ProtocolAttributes(                    
                    type = ProtocolAttributes.TYPE_INITIAL_SECURITY_NOTIFICATION_SETTING_SYNC,
                    initial_security_notification_setting_sync=  InitialSecurityNotificationSettingSyncAttribute(
                        security_notification_enabled=True
                    )
                ),message_meta_attributes=MessageMetaAttributes(
                    recipient=companionJid,
                    category="peer"
                ))

                await self.toLower(entity)                
                sync_keys = self.generateAppStateSyncKeys(10)

                if self.db:
                    self.db._store.addAppStateKeys(sync_keys)

                entity = ProtocolMessageProtocolEntity(protocol_attr=ProtocolAttributes(                    
                    type  = ProtocolAttributes.TYPE_APP_STATE_SYNC_KEY_SHARE,
                    app_state_sync_key_share= AppStateSyncKeyShareAttribute(
                        keys = sync_keys
                    )

                ),message_meta_attributes=MessageMetaAttributes(
                    recipient=companionJid,
                    category="peer"
                ))        
                
                await self.toLower(entity)
                await asyncio.sleep(3)           

                async def on_get_conn_success(conn_entity, original_iq_entity):   

                    hs = HistorySync(conn_entity,companionJid)

                    et = hs.createNonBlockingDataMessage()
                    await self.toLower(et)
                    et = hs.createInitialStatusV3Message()
                    await self.toLower(et)
                    et = hs.createPushNameMessage()
                    await self.toLower(et)
                    et = hs.createInitialBootstrapMessage(conversations=[ConversationAttribute(id="TEST")])
                    await self.toLower(et)
                    et = hs.createRecentMessage()
                    await self.toLower(et)
                    
                    et = TrustContactIqProtocolEntity(Jid.normalize(self.bot.botId),int(time.time()))
                    await self.toLower(et)

                    #######################APP STATE SYNC START###############################

                    #  critical_block critical_unblock_low
                    if not self.db:
                        return 
                    
                    key = self.db._store.getOneAppStateKey()  
                    mutationKeys = MutationKeys.createFromKey(key.key_data.key_data)

                    localeSetting = SyncActionDataAttribute.createFromSyncActionValue(SyncActionValueAttribute(
                                localeSetting=SyncActionLocaleSettingAttribute(locale="zh_CN")
                            ))     
                    pushNameSetting = SyncActionDataAttribute.createFromSyncActionValue(SyncActionValueAttribute(
                                pushNameSetting=SyncActionPushnameSettingAttribute(name="enx test")                            
                            ))    

                    state = HashState("critical_block",0)                        
                    state,syncdPatch1 = PatchBuilder(state,mutationKeys,key).addMutation(localeSetting).addMutation(pushNameSetting).finish()                                                            
     
                    name1 = SyncActionDataAttribute.createFromSyncActionValue(SyncActionValueAttribute(
                                contactAction=SyncActionContactActionAttribute(fullName="test user",firstName="test",lidJid="8618502060000@s.whatsapp.net")                           
                            ).setArgs(["8618502060000@s.whatsapp.net"]))     
         

                    state2 = HashState("critical_unblock_low",0)
                    state2,syncdPatch2  = PatchBuilder(state2,mutationKeys,key).addMutation(name1).finish()

                                      
                    entity = AppSyncStateIqProtocolEntity(
                        patches = {
                            "critical_unblock_low":syncdPatch2.encode(),
                            "critical_block":syncdPatch1.encode()
                        }                    
                    )

                    await self.toLower(entity)

                def on_get_conn_error(entity, original_iq_entity):  
                    self.logger.error("get conn error")

                conniq = RequestMediaConnIqProtocolEntity()
                await self._sendIq(conniq,on_get_conn_success,on_get_conn_error)

            def on_get_encrypt_error(entity, on_get_encrypt_error):
                self.logger.error("error get encrypt")

            await self._sendIq(entity, on_get_encrypt_success, on_get_encrypt_error)                 

        if isinstance(entity,LinkCodeCompanionRegNotificationProtocolEntity):
            self.logger.info("Notification: Received a LinkCodeCompanionReg, stage=%s",entity.stage)

            if entity.stage == "primary_hello":                
                linkCode = self.bot.pairLinkCode
                #这个时候是配对请求，直接回复一个hello就行了
                #丢到应用层处理            
                primaryEphemeralPub = Utils.link_code_decrypt(linkCode,entity.linkCodePairingWrappedPrimaryEphemeralPub)                                
                shareEphemeralSecret = Curve.calculateAgreement(DjbECPublicKey(primaryEphemeralPub),DjbECPrivateKey(self.getProp("reg_info")["keypair"].private.data))                                
                linkCodePairingEphemeralRootSecret = get_random_bytes(32)
                encryptPayload  = self.getProp("reg_info")["identity"].publicKey.serialize()[1:]+entity.primaryIdentityPublic+linkCodePairingEphemeralRootSecret
                companionFinishKdfSalt = get_random_bytes(32)
                linkCodePairingKeyBundleEncryptionKey = Utils.extract_and_expand(shareEphemeralSecret,b"link_code_pairing_key_bundle_encryption_key",32,companionFinishKdfSalt)                
                companionFinishIV  = get_random_bytes(12)
                cipher = AESGCM(linkCodePairingKeyBundleEncryptionKey)
                encrypted  = cipher.encrypt(companionFinishIV,encryptPayload, b'')                
                encryptedPayload = companionFinishKdfSalt + companionFinishIV + encrypted
                identitySharedKey = Curve.calculateAgreement(DjbECPublicKey(entity.primaryIdentityPublic),DjbECPrivateKey(self.getProp("reg_info")["identity"].privateKey.serialize()))
                linkingSecretKeyMaterial = shareEphemeralSecret+identitySharedKey+linkCodePairingEphemeralRootSecret
                advSecretPublicKey = Utils.extract_and_expand(linkingSecretKeyMaterial,b"adv_secret",32)                  
                entity = MultiDevicePairCompanionFinishIqProtocolEntity(self.bot.pairPhoneNumber+"@s.whatsapp.net",encryptedPayload, self.getProp("reg_info")["identity"].publicKey.serialize()[1:],entity.linkCodePairingRef)
                await self.toLower(entity)

                return 
                                                
            if entity.stage == "companion_hello":            

                logger.info("ENTERING WAITING CODE STATUS")
                self.pairingStatus = "WAIT_PAIRINGCODE"
                self.companionHelloEntity = entity  

                logger.debug("bot_type: %s", self.bot.bot_type)

                if self.bot.bot_type == ZowBotType.TYPE_RUN_TEMP:
                    #如果是临时模式TYPE_RUN_TEMP模式，直接输入，不需要再调用接口
                    await self.executeCommand("md.inputcode", ["AAAAAA"])                    
                                                  
            if entity.stage == "companion_finish":
                if self.getProp("keypair") is None:
                    return 

                ref = entity.linkCodePairingRef
                primaryEphemerKeyPair = self.getProp("keypair")
                companionEphemerPub = self.getProp("companionEphemerPub")
                companionIdentityPublic = entity.companionIdentityPublic
                companionServerAuthKeyPub = self.getProp("companionAuthKeyPub")
                companionFinishKdfSalt = entity.linkCodePairingWrappedKeyBundle[:32]
                companionFinishIV = entity.linkCodePairingWrappedKeyBundle[32:44]
                linkCodePairingEncryptedKeyBundle = entity.linkCodePairingWrappedKeyBundle[44:]
                shareEphemeralSecret = Curve.calculateAgreement(DjbECPublicKey(companionEphemerPub),DjbECPrivateKey(self.getProp("keypair").private.data))
                linkCodePairingKeyBundleEncryptionKey = Utils.extract_and_expand(shareEphemeralSecret,b"link_code_pairing_key_bundle_encryption_key",32,companionFinishKdfSalt)
                cipher = AESGCM(linkCodePairingKeyBundleEncryptionKey)
                linkCodePairingKeyBundle  = cipher.decrypt(companionFinishIV,linkCodePairingEncryptedKeyBundle, b'')                     
                identitySharedKey = Curve.calculateAgreement(DjbECPublicKey(companionIdentityPublic),DjbECPrivateKey(self.db.identity.privateKey.serialize()))
                linkCodePairingEphemeralRootSecret = linkCodePairingKeyBundle[-32:]
                linkingSecretKeyMaterial = shareEphemeralSecret+identitySharedKey+linkCodePairingEphemeralRootSecret
                advSecretPublicKey = Utils.extract_and_expand(linkingSecretKeyMaterial,b"adv_secret",32)                  
                await self.resetSync([],{})                
                profile = self.getProp("profile")
                ref,pubKey,deviceIdentity,keyIndexList = Utils.generateMultiDeviceParams(ref,companionServerAuthKeyPub,companionIdentityPublic,advSecretPublicKey,profile)                                                
                entity = MultiDevicePairDeviceIqProtocolEntity(ref=ref,pubKey=pubKey,deviceIdentity=deviceIdentity,keyIndexList=keyIndexList)                

                def on_pair_device_success(entity, original_iq_entity):                    
                    companionJid = entity.deviceJid
                    deviceIdx =  int(companionJid.split("@")[0].split(":")[1])
                    profile.config.add_device_to_list(deviceIdx)
                    profile.write_config(profile.config)
                    self.getStack().setProp("pair-companion-jid",companionJid)
                    
                def on_pair_device_error(entity, original_iq):         
                    logger.error("pair device error")               
                    self.bot.quit()            

                await self._sendIq(entity, on_pair_device_success, on_pair_device_error)                

        if isinstance(entity,WaOldCodeNotificationProtocolEntity):
            self.logger.info(f"Notification: Received a wa_old registration code: {entity.code} in {entity.timestamp}")  
            if self.getProp("TRANSFER6_MODE",False):
                if int(entity.timestamp)>=self.bot.startts:
                    self.bot.wa_old = entity.code     
                    self.callback(modeResult = {
                        "retcode":0,
                        "code":entity.code   
                    })           
            return                     

        if isinstance(entity,DeviceLogoutNotificationProtocolEntity):
            self.logger.info(f"Notification: device_logout request from {entity.device} with refId = {entity.refId} in {entity.timestamp}")                  
            self.logoutApprove([entity.refId],{})
            return 
                    
        if isinstance(entity,CreateGroupsNotificationProtocolEntity):
            self.logger.info("Notification: Group %s created" % entity.groupId)
            return 
        
        if isinstance(entity,AddGroupsNotificationProtocolEntity):            
            self.logger.info(f"Notification: Group {entity.getGroupId()} add participant {entity.getParticipants()[0]}")
            return
        
        if isinstance(entity,RemoveGroupsNotificationProtocolEntity):             
            self.logger.info(f"Notification: Group {entity.getGroupId()} remove participant {entity.getParticipants()[0]}")       
            return    
        
        if isinstance(entity,SetPictureNotificationProtocolEntity):
            if entity.setJid is not None:
                self.callback({
                    "event":zowsup_pb2.BotEvent.Event.CONTACT_UPDATE,
                    "detail":{
                        "target":entity.setJid,
                        "key":"AVATAR",
                        "value":entity.setId
                    }
                })
            return      

        if isinstance(entity,BusinessNameUpdateNotificationProtocolEntity):
            if entity.name is not None:
                if entity.jid.endswith("@lid"):
                    self.db._store.updateContact(None,lid = entity.jid,name=entity.name)                    
                else:
                    self.db._store.updateContact(jid = entity.jid,lid = None,name=entity.name)

                self.callback({
                    "event":zowsup_pb2.BotEvent.Event.CONTACT_UPDATE,
                    "detail":{
                        "target":entity.jid,
                        "key":"NAME",
                        "value":entity.name
                    }                    

                })                
            return                

    def setCmdResult(self,cmdId,result):
        self.bot.setCmdResult(cmdId,result)

    def setCmdError(self,cmdId,error):        
        self.bot.setCmdError(cmdId,error)

    @ProtocolEntityCallback("presence")            
    def onPresence(self,entity):
        if isinstance(entity,PresenceProtocolEntity):
            self.setCmdResult(entity.getId(),{
                "type":entity.getType(),
                "last":entity.getLast()
            })
            return
                         
    @ProtocolEntityCallback("iq")
    async def onIq(self, entity):          

        if self.getProp("TRANSFER6_MODE",False):
            if time.time()-self.bot.startts > 300:
                #300秒都还没搞完，直接退了
                self.bot.quit()

        self.pingCount+=1
        if self.pingCount % 10 == 0:        
            self.callback(event={"event":zowsup_pb2.BotEvent.Event.HEARTBEAT})
                        
        if isinstance(entity,ResultIqProtocolEntity):
            #这里主要处理一些非指令产生的回复,例如ping            
            self.setCmdResult(entity.getId(),{"status":"ok"})
            return 
        
        if isinstance(entity,ErrorIqProtocolEntity):
            self.setCmdError(entity.getId(),entity.code)
            return 
                                         
        if isinstance(entity, MultiDevicePairIqProtocolEntity):                  

            def on_success(entity, original_iq_entity):       
                self.logger.info("Pairing Start Success")            

            def on_error(entity, original_iq):                                        
                self.logger.error(f"Pairing Start Fail with code {entity.code} - {entity.text} ")                           

            if self.getProp("botType")==ZowBotType.TYPE_REG_COMPANION_SCANQR:
                logger.info("QRCode Pairing")
                ack = IqProtocolEntity(to = YowConstants.WHATSAPP_SERVER,_type="result",_id=entity.getId())       
                await self._sendIq(ack)     
                self.setProp("refs",entity.refs)
                #开始一个展示二维码的asyncio task
                self._qrTask = asyncio.ensure_future(_qr_code_task(self, 20))
                return 
            elif self.getProp("botType")==ZowBotType.TYPE_REG_COMPANION_LINKCODE:
                logger.info("LinkCode Pairing")
                ack = IqProtocolEntity(to = YowConstants.WHATSAPP_SERVER,_type="result",_id=entity.getId())
                await self._sendIq(ack)
                identity = self.getProp("reg_info")["identity"]                
                linkCodePairingWrappedCompanionEphemeralPub = Utils.link_code_encrypt(self.bot.pairLinkCode,self.getProp("reg_info")["keypair"].public.data)
                companionServerAuthKeyPub = self.getProp("reg_info")["keypair"].public.data
                jid = self.bot.pairPhoneNumber+"@s.whatsapp.net"                
                entity = MultiDevicePairCompanionHelloIqProtocolEntity(jid,shouldshowPushNotification="true",linkCodePairingWrappedCompanionEphemeralPub=linkCodePairingWrappedCompanionEphemeralPub,companionServerAuthKeyPub=companionServerAuthKeyPub)                
                await self._sendIq(entity,on_success,on_error)                
                
                return 

        if isinstance(entity, MultiDevicePairSuccessIqProtocolEntity):                               
            jid = entity.jid
            print(jid, flush=True)  # signal login success to dashboard SSE stream
            self.setProp("refs",None)          
            self.setProp("jid",jid)     
            self.setProp("botType",ZowBotType.TYPE_RUN_SINGLETON)
            p1 = wa_struct_pb2.ADVSignedDeviceIdentityHMAC()
            p1.ParseFromString(entity.device_identity)        
            p2 = wa_struct_pb2.ADVSignedDeviceIdentity()
            p2.ParseFromString(p1.details)
            p3 = wa_struct_pb2.ADVDeviceIdentity()
            p3.ParseFromString(p2.details)        
            identity = self.getProp("reg_info")["identity"]
            buffer=b'\x06\x01'+p2.details+identity.publicKey.serialize()[1:]+p2.account_signature_key            
            devicesign = Curve.calculateSignature(identity.privateKey,buffer)
            p4 = wa_struct_pb2.ADVSignedDeviceIdentity()            
            p4.account_signature_key = p2.account_signature_key
            p4.account_signature = p2.account_signature
            p4.details = p2.details
            p4.device_signature = devicesign
            signEntity = MultiDevicePairSignIqProtocolEntity(entity.getId(),p3.key_index,p4.SerializeToString())       
            await self._sendIq(signEntity)                 
            self.genProfile(p4) 
            return 
              
    @ProtocolEntityCallback("failure")
    def onFailure(self, entity):
        self.logger.info("Login Fail")     
        self.loginFailCount+=1        
        if entity.reason=="403" or entity.reason=="401" or entity.reason=="405" or entity.reason=="404":
            if entity.violation_type is not None:
                reason = entity.reason+":"+Utils.violationTypeName(int(entity.violation_type))
            else:
                reason = entity.reason

            self.callback(event={
                "event":zowsup_pb2.BotEvent.Event.LOGIN_FAIL,
                "detail":reason
            })
            
            # Clear botId on login failure for proper state cleanup
            if entity.reason in ["403", "401", "405"]:
                old_botId = self.bot.botId
                self.bot.botId = None
                self.logger.debug(f"Cleared botId due to login failure ({entity.reason}): {old_botId}")

            self.detect40x = True            

            if entity.reason != "405" and self.bot.bot_type != ZowBotType.TYPE_RUN_TEMP:                
                self.bot.quit()

            self.loginEvent.set()        

            if self.getProp("HC_MODE"):                                
                self.db._store.identityKeyStore.dbConn.close()      #断开连接，方便外层删除数据
                self.callback(modeResult= {                        
                    "retcode":-1,
                    "detail":reason
                })

                #Utils.fail_exit(entity.reason)

    def callback(self,event=None,message=None,messageStatus=None,cmdResult=None,modeResult=None):           
        self.bot.callback(event,message,messageStatus,cmdResult,modeResult)


    @ProtocolEntityCallback("success")
    async def onSuccess(self, successProtocolEntity):      

        if self.getProp("HC_MODE"):            
            self.db._store.identityKeyStore.dbConn.close()      #断开连接，方便外层删除数据
            self.callback(modeResult={
                "botId":self.bot.botId,
                "retcode":0,
                "detail":None
            })                

        if self.getProp("TRANSFER6_MODE"):
            # Execute account setup commands using the generic command interface
            try:
                await self.executeCommand("account.set2fa", ["",""])    #获取wa_old前，也同步重置2fa先
                await self.executeCommand("account.setemail", [""])     #清理原来绑定的邮箱
                await self.executeCommand("account.setname")            #business必须设置一个名称，否则无法收到消息
                await self.executeCommand("account.info", [])           #获取到原来的帐号的注册时间信息
            except Exception as e:
                self.logger.error(f"Failed to execute account setup commands: {e}")
                # Continue despite errors, don't block the login flow

        if self.bot.profile.config.lid is None:
            profile = self.getStack().getProp("profile")
            profile.config.lid = successProtocolEntity.lid            
            profile.write_config()
                             
        self.callback(event={
            "event":zowsup_pb2.BotEvent.Event.LOGIN_SUCCESS            
        })                               

        if self.getProp("REPAIRFCM",False) and not self.getProp("REPAIRFCM_ING", False) :
            logger.info("START REPAIRING FCM")            
            await self.executeCommand("misc.regfcm", [],{})            
            self.setProp("REPAIRFCM_ING", True)   
                            
        self.isConnected = True
        self.loginEvent.set()  
        entity = AvailablePresenceProtocolEntity()
        await self.toLower(entity)         
        self.bot.status = ZowBotStatus.STATUS_RUNNING   

        self.bot.lastOnlineTime = int(time.time()) 

        self.loginFailCount = 0
        #self.setProp(PROP_IDENTITY_AUTOTRUST, True)
        
    @ProtocolEntityCallback("stream:error")
    async def onStreamError(self, entity):
        self.logger.info("Stream Error")           
        self.logger.debug(entity)
        self.bot.status = ZowBotStatus.STATUS_ERROR

        if entity.getErrorType()=="conflict":
            self.bot.conflict = True

            self.callback(event={
                "event":zowsup_pb2.BotEvent.Event.CONFLICT            
            })              
            
        if entity.code is not None :
            if entity.code=="503":
                self.detect503 = True      
                await self.bot._stack.broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT))                
   
    @ProtocolEntityCallback("ack")
    def onAck(self, entity):                
        
        if entity.getId() in self.ackQueue:

            if entity._from is not None:
                num = entity._from[0:entity._from.rfind('@', 0)]       
            else:
                num = "UNKNOWN"           

            if entity.getError() is None:     

                self.callback(messageStatus={
                    "msgId":entity.getId(),
                    "target":num,
                    "status":zowsup_pb2.MessageStatus.SENT
                    
                })          

            else:                

                self.callback(messageStatus={
                    "msgId":entity.getId(),
                    "target":num,
                    "status":zowsup_pb2.MessageStatus.ERROR,
                    "errorCode":entity.getError()
                    
                })                                    
            
                                
            self.ackQueue.pop(self.ackQueue.index(entity.getId()))            
               
    def download(self,params):
                    
        enc_data = requests.get(url=params["url"]).content

        if enc_data is None:            
            logger.error("Download failed")        
            return None
        
        filename = params["filename"]
        ext = None

        match params["type"]:
            case "IMAGE":
                media_info = MediaCipher.INFO_IMAGE            
            case "VIDEO":
                media_info = MediaCipher.INFO_VIDEO    
            case "AUDIO":
                media_info = MediaCipher.INFO_AUDIO
            case "DOCUMENT":
                media_info = MediaCipher.INFO_DOCUMENT
            case "STICKER":
                media_info = MediaCipher.INFO_IMAGE
            case _:
                logger.error("Unsupported type")
                return None  

        filedata = MediaCipher().decrypt(enc_data, params["media_key"], media_info)
        
        if filedata is None:
            logger.error("Decrypt failed")
            return None
        
        if params["mimetype"]=="application/was":
            ext = ".was"
        
        if ext is None:
            ext = mimetypes.guess_extension(params["mimetype"].split(";")[0])
                            
        try:
            filename = SysVar.DOWNLOAD_PATH+filename+ext
            with open(filename, 'wb') as f:
                f.write(filedata)            
            
        except Exception as e:                       
            logger.error(e)
            return None
        
        return filename
    
    def parseMediaCommonAttributes(self,msg,media_specific_attributes):        
        if media_specific_attributes is not None:
            msg.url = media_specific_attributes.url
            msg.direct_path = media_specific_attributes.direct_path
            msg.file_enc_sha256 = media_specific_attributes.file_enc_sha256
            msg.media_key_timestamp = media_specific_attributes.media_key_timestamp
            msg.file_sha256 = media_specific_attributes.file_sha256
            msg.file_length = media_specific_attributes.file_length
            msg.mimetype = media_specific_attributes.mimetype
            msg.media_key = media_specific_attributes.media_key
    
    async def _async_send_message_acks(self, messageProtocolEntity):
        """
        Send message acknowledgments with probabilistic behavior.
        
        - Sends first ack (received notification) with 80% probability        
        - Then sends second ack (read notification)
        """

        if random.random() < 0.8:
            await self.toLower(messageProtocolEntity.ack())            
        else:
            logger.debug("Not sending received ack for message %s" % messageProtocolEntity.getId())
        
        # Always send read ack
        await self.toLower(messageProtocolEntity.ack(read=True))
    
    def _parse_jid_and_lid(self, messageProtocolEntity):
        """
        Parse and extract JID and LID from messageProtocolEntity.
        
        Returns:
            tuple: (jid, lid) - the normalized JID and LID
        """
        _from = messageProtocolEntity.getFrom()
        
        if _from.endswith("lid"):
            lid = Utils.normalize_jid(_from)
            jid = messageProtocolEntity.getSenderPn()
            # sender_pn is sometimes absent; fall back to notify if it looks like a JID
            if not jid:
                notify = messageProtocolEntity.getNotify()
                if notify and notify.endswith("s.whatsapp.net"):
                    jid = notify
        else:
            jid = Utils.normalize_jid(_from)
            lid = messageProtocolEntity.getSenderLid()
        
        return jid, lid
    
    def _parse_message_type(self, messageProtocolEntity):
        """
        Parse message type and extract text from messageProtocolEntity.
        
        Returns:
            tuple: (message_type, text) where:
                - message_type: zowsup_pb2.MessageType enum value
                - text: str, the message text content
        """
        msg_type = messageProtocolEntity.getType()
        message_type = zowsup_pb2.MessageType.UNKNOWN_MEDIA
        text = ""
        
        if msg_type == 'text':
            message_type = zowsup_pb2.MessageType.TEXT
            if isinstance(messageProtocolEntity, TextMessageProtocolEntity):
                text = messageProtocolEntity.getBody()
            elif isinstance(messageProtocolEntity, ExtendedTextMessageProtocolEntity):
                text = messageProtocolEntity.text
                if (messageProtocolEntity.context_info is not None and 
                    messageProtocolEntity.context_info.external_ad_reply is not None):
                    message_type = zowsup_pb2.MessageType.AD
        
        elif msg_type == 'reaction':
            self.logger.debug("reaction entity: %s", messageProtocolEntity)
            if isinstance(messageProtocolEntity, ReactionMessageProtocolEntity):
                message_type = zowsup_pb2.MessageType.REACTION
                text = (messageProtocolEntity.message_attributes.reaction.text 
                        if messageProtocolEntity.message_attributes.reaction else "[reaction]")
        
        elif msg_type == 'poll':
            message_type = zowsup_pb2.MessageType.POLL
            if isinstance(messageProtocolEntity, PollCreationMessageProtocolEntity):
                text = "[poll create]"
            elif isinstance(messageProtocolEntity, PollUpdateMessageProtocolEntity):
                text = "[poll update]"
        
        elif msg_type == 'media':
            if isinstance(messageProtocolEntity, ExtendedTextMediaMessageProtocolEntity):
                message_type = zowsup_pb2.MessageType.URL
                text = messageProtocolEntity.text
                if (messageProtocolEntity.media_specific_attributes.context_info is not None and 
                    messageProtocolEntity.media_specific_attributes.context_info.external_ad_reply is not None):
                    message_type = zowsup_pb2.MessageType.AD
                    text = messageProtocolEntity.media_specific_attributes.context_info.external_ad_reply.source_url
            
            elif isinstance(messageProtocolEntity, ImageDownloadableMediaMessageProtocolEntity):
                message_type = zowsup_pb2.MessageType.IMAGE
                text = "[image]"
            
            elif isinstance(messageProtocolEntity, VideoDownloadableMediaMessageProtocolEntity):
                message_type = zowsup_pb2.MessageType.VIDEO
                text = "[video]"
            
            elif isinstance(messageProtocolEntity, AudioDownloadableMediaMessageProtocolEntity):
                message_type = zowsup_pb2.MessageType.AUDIO
                text = "[audio]"
            
            elif isinstance(messageProtocolEntity, DocumentDownloadableMediaMessageProtocolEntity):
                message_type = zowsup_pb2.MessageType.DOCUMENT
                text = "[document]"
            
            elif isinstance(messageProtocolEntity, StickerDownloadableMediaMessageProtocolEntity):
                message_type = zowsup_pb2.MessageType.STICKER
                text = "[sticker]"
            
            else:
                message_type = zowsup_pb2.MessageType.UNKNOWN_MEDIA
                text = "[media]"
        
        return message_type, text
    
    @ProtocolEntityCallback("message")
    async def onMessage(self, messageProtocolEntity):         
        
        # Parse JID and LID from message entity
        jid, lid = self._parse_jid_and_lid(messageProtocolEntity)
   
        if self.db:
            notify = messageProtocolEntity.getNotify()
            # Don't store a JID-formatted string as a display name
            contact_name = None if (notify and '@' in notify) else notify
            self.db._store.updateContact(jid=jid, lid=lid, name=contact_name)

        # Parse message type and extract text
        type, text = self._parse_message_type(messageProtocolEntity)
          
        if isinstance(messageProtocolEntity, ProtocolMessageProtocolEntity): 
            protocol_attrs = None
            if messageProtocolEntity.message_attributes is not None:
                protocol_attrs = messageProtocolEntity.message_attributes.protocol

            if protocol_attrs is not None and protocol_attrs.type in (
                ProtocolAttributes.TYPE_HISTORY_SYNC_NOTIFICATION,
                ProtocolAttributes.TYPE_APP_STATE_SYNC_KEY_SHARE,
            ):
                #历史消息同步，发送一个hist_sync确认回执就结束，不回调,没有READ                
                await self.toLower(messageProtocolEntity.ack(histSync=True))
                return 
                    
            elif messageProtocolEntity.category=="peer":
                #app state sync key share，同样发送一个ack就结束
                await self.toLower(messageProtocolEntity.ack(peerMsg=True))
                return
                          
        self.callback(message={
            "type":type,
            "text":text,
            "msgId":messageProtocolEntity.getId(),
            "from":messageProtocolEntity.getFrom(False),
            "to":messageProtocolEntity.getTo(False) if messageProtocolEntity.fromme else self.bot.botId,
            "timestamp":int(time.time()),            
            "raw":base64.b64encode(messageProtocolEntity.raw)
        })

        # Send message acks with probabilistic behavior
        await self._async_send_message_acks(messageProtocolEntity)        
                                                                
    @ProtocolEntityCallback("receipt")
    async def onReceipt(self, entity):

        if entity.getParticipant() is not None:
            num = entity.getFrom(False)+"::"+entity.getParticipant(False)
        else:
            num = entity.getFrom(False)
            
        #群发模式，有待跟踪的消息id                          
        if entity.getType() == "read":
            self.callback(messageStatus={
                "msgId":entity.getId(),
                "target":num,
                "status":zowsup_pb2.MessageStatus.READ
                
            })                            
        else:
            self.callback(messageStatus={
                "msgId":entity.getId(),
                "target":num,
                "status":zowsup_pb2.MessageStatus.DELIVERED
                
            })                           

        await self.toLower(entity.ack())        
                      
    def waitLogin(self):
        #等待bot连接就绪,
        #超时返回false，正常登录返回true        
        return self.loginEvent.wait(20)
            
    async def assureContactsAndSend(self,cmdParams,options,send_func,redo_func):        
        to,*other = cmdParams
        isCompanion = "_" in self.bot.botId
        jid = Jid.normalize(to)
        if jid.endswith("@g.us"):
            # Group JIDs need no contact-sync — send directly
            await send_func(cmdParams, options)
        elif not jid.endswith("@lid"):
            foundContact = self.db._store.findContact(jid)        
            if not foundContact and not isCompanion:                
                entity = ContactGetSyncIqProtocolEntity([to],mode = "delta")    
                result_dict = await self._sendIqAsync(entity)                
                if isinstance(result_dict["result"], ContactResultSyncIqProtocolEntity):
                    logger.info("add target to contacts")      
                                        
                    jid = []
                    for key,value in result_dict["result"].result.items():
                        if value["type"]=="in":                        
                            self.db._store.updateContact(value["jid"],value["lid"],key)      
                            jid.append(value["jid"])
                        else:
                            logger.info("%s not found",key)
                    if len(jid)>0:
                        cmdParams[0]=','.join(jid)
                        await redo_func(cmdParams,options)                
                    else:
                        logger.error("target not found in contacts")
                else:
                    logger.error("ERROR on _sendIq")   

            else:
                logger.info("target in contacts")                       
                await send_func(cmdParams,options)                         
        else:
            logger.info("lid-target, direct send")  
            await send_func(cmdParams,options)                             

    async def getContactList(self, cmdParams, options):
        query = {
            "variables": {
                "batch_size": 3000,
                "include_encrypted_metadata_v2": False,
                "include_lid_info": True,
                "input": {
                    "query_input": [{"jid": Jid.normalize(cmdParams[0])}],
                    "telemetry": {"context": "REGISTRATION"}
                }
            }
        }
        entity = WmexQueryIqProtocolEntity(query_name="SelfContactsQuery", query_obj=query)
        try:
            result_dict = await self._sendIqAsync(entity)
            entity_result = result_dict["result"]
            
            if isinstance(entity_result, WmexResultIqProtocolEntity):
                return {"result": entity_result.result_obj}
            else:
                raise Exception(f"Unexpected response type: {type(entity_result)}")
        except Exception as e:
            logger.error(f"getContactList error: {e}")
            raise     
    
    def getContextValue(self,ctxId,key):
        if ctxId not in self.ctxMap:
            return None        
        if key not in self.ctxMap[ctxId]:
            return None        
        return self.ctxMap[ctxId][key]

    def setMode(self,mode):
        self.mode = mode

    async def fcmMsgCallback(self,obj,data,p):        
        logger.info("fcm msg callback")        
        
        entity = PushGetCatIqProtocolEntity(token=data["pn"])
        result = await self._sendIqAsync(entity)
        print(result)

        result_entity = result.get("result")        
        if isinstance(result_entity, PushGetCatResultIqProtocolEntity):
            profile = self.getStack().getProp("profile")
            profile.config.fcm_cat = base64.b64encode(result_entity.catData)
            profile.write_config()
            logger.info("get fcm cat success")                        
            await self.bot._stack.broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT)) 
        else:
            logger.error("get fcm cat failed")

    async def resetSync(self,params,options):        
        try:
            entity = AppSyncResetIqProtocolEntity()
            await self.toLower(entity)  
            logger.info("resetSync ok")
        except Exception as e:
            logger.error(f"resetSync error: {e}")
            raise        

    def generateAppStateSyncKeys(self,n):
        profile = self.getStack().getProp("profile")        
        keys = []
        for i in range(0,n):
            key = AppStateSyncKeyAttribute(
                key_id= AppStateSyncKeyIdAttribute(key_id=random.randint(10000,20000).to_bytes(6,'big')),
                key_data=AppStateSyncKeyDataAttribute(
                    key_data=Curve.generateKeyPair().publicKey.serialize()[1:],
                    fingerprint=AppStateSyncKeyFingerprintAttribute(
                       raw_id = random.randint(10000,2000000000),
                       current_index=i,
                       device_indexes=profile.config.device_list
                    ),
                    timestamp=int(time.time())
                )
            )
            keys.append(key)        
        return keys
    
    
    async def logoutApprove(self,cmdParams,options):
        entity = AccountLogoutApproveIqProtocolEntity(cmdParams[0])        
        await self._sendIqAsync(entity)
        return {
            "retcode": 0
        }    
    
    async def syncData(self,cmdParams,options):
        request = {}             
        collectionNames = cmdParams[0].split(",")
        for name in collectionNames:
            request[name] = {                    
                "version":"0",
                "return_snapshot":True
            }

        entity = AppSyncStateIqProtocolEntity(                            
            request = request
        )            
        #直接用服务器返回的版本去请求，表明companion有一致的数据
        try :
            while entity is not None:
                result_dict = await self._sendIqAsync(entity)
                entity_result = result_dict["result"]
                if isinstance(entity_result, ResultAppSyncStateIqResponseProtocolEntity):
                    requestNext = {}
                    for key,item in entity.collections.items():
                        name = key
                        if "error" in item and item["error"]["code"]=="409":    
                            requestNext[name] = {
                                "version" : str(int(entity.request[name]["version"])+1)   #升一个版本号，继续请求
                            }
                        else :
                            #这里是没有冲突的数据更新,目前副端的数据暂时不解密
                            pass

                    if len(requestNext)>0:
                        entity = AppSyncStateIqProtocolEntity(                            
                            request = requestNext
                        )
                        continue                        
                    else:
                        entity = None   #没有需要继续请求的了，结束循环
                else:
                    raise Exception(f"Unexpected response type: {type(entity_result)}")
        
        except asyncio.TimeoutError as e:
            logger.warning("syncData timeout (collections=%s): %s", cmdParams[0], e)
        except Exception as e:
            logger.error("syncData error: %s", e, exc_info=True)

