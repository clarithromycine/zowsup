import os,sys
sys.path.append(os.getcwd())

# coding=UTF-8

from yowsup.common import YowConstants
from yowsup.layers import EventCallback, YowLayerEvent
from yowsup.layers.axolotl.protocolentities.iq_keys_get_result import ResultGetKeysIqProtocolEntity
from yowsup.layers.interface  import YowInterfaceLayer, ProtocolEntityCallback
from yowsup.layers.network.layer import YowNetworkLayer
from yowsup.layers.protocol_messages.protocolentities  import *
from yowsup.layers.protocol_messages.protocolentities.attributes import *
from yowsup.layers.protocol_chatstate.protocolentities import *
from yowsup.layers.protocol_notifications.protocolentities import *
from yowsup.layers.protocol_presence.protocolentities.presence import PresenceProtocolEntity
from yowsup.layers.protocol_profiles.protocolentities  import *
from yowsup.layers.protocol_contacts.protocolentities  import *
from yowsup.layers.protocol_iq.protocolentities  import *
from yowsup.layers.protocol_ib.protocolentities  import *
from yowsup.layers.protocol_media.protocolentities  import *
from yowsup.layers.protocol_groups.protocolentities  import * 
from yowsup.layers.protocol_privacy.protocolentities  import *
from yowsup.layers.axolotl.props import PROP_IDENTITY_AUTOTRUST
from google.protobuf.json_format import MessageToDict

from yowsup.layers.protocol_presence.protocolentities import *

from yowsup.layers.protocol_ib.protocolentities import *
from yowsup.config.v1.config import Config
from common.utils import Utils
from yowsup.common.tools import WATools
from yowsup.layers.protocol_media.mediacipher import MediaCipher

from yowsup.common.tools import Jid
import requests,logging,io,os,time,mimetypes,base64,random,threading,qrcode

from yowsup.common.optionalmodules import PILOptionalModule
from conf.constants import SysVar
from threading import Thread

from proto import wsend_pb2,wa_struct_pb2

from yowsup.profile.profile import YowProfile
from pathlib import Path
from .yowbot_values import YowBotType
from axolotl.ecc.curve import Curve

from yowsup.layers.protocol_presence.protocolentities.presence_subscribe import SubscribePresenceProtocolEntity

import uuid,traceback
from app.param_not_enough_exception import ParamsNotEnoughException

logger = logging.getLogger(__name__)

class YowQrCodeThread(Thread):
    def __init__(self, layer, interval):
        assert type(layer) is SendLayer, "layer must be a SenderLayer, got %s instead." % type(layer)
        
        self._layer = layer
        self._interval = interval
        self._stop = False
        self.__logger = logging.getLogger(__name__)
        super(YowQrCodeThread, self).__init__()
        self.daemon = True
        self.name = "YowQrCode-%s" % self.name
    
    def run(self):
        while not self._stop:
            refs = self._layer.getProp("refs")
            if len(refs)>0:
                ref = refs.pop(0)
                regInfo = self._layer.getProp("reg_info")
                keypair = regInfo["keypair"]
                identity = regInfo["identity"]                
                advSecretKey = random.randbytes(32)
                print("%s,%s,%s,%s" % (
                    str(ref,"utf8"),
                    str(base64.b64encode(keypair.public.data),"utf8"),
                    str(base64.b64encode(identity.publicKey.serialize()[1:]),"utf8"),
                    str(base64.b64encode(advSecretKey),"utf8")
                ))
                qr = qrcode.QRCode()
                qr.border =1
                qr.add_data("%s,%s,%s,%s" % (
                    str(ref,"utf8"),
                    str(base64.b64encode(keypair.public.data),"utf8"),
                    str(base64.b64encode(identity.publicKey.serialize()[1:]),"utf8"),
                    str(base64.b64encode(advSecretKey),"utf8")
                ))
                qr.make()
                qr.print_ascii(out=None,tty=False,invert=False)                                                
                self._layer.setProp("refs",refs)
            else:
                self._stop = True                                                   
                self._layer.getStack().broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT))
            for i in range(0, self._interval):                
                time.sleep(1)                
                if self._stop:
                    self.__logger.debug("%s - QrThread stopped" % self.name)
                    return

    def stop(self):
        self._stop = True        

class SendLayer(YowInterfaceLayer):

    PROP_MESSAGES = "org.openwhatsapp.yowsup.prop.sendclient.queue"
    PROP_WAAPI  = "org.openwhatsapp.yowsup.prop.sendclient.waapi"  

    def __init__(self,bot):
        super(SendLayer, self).__init__()
        self.ackQueue = []        
        self.isConnected = False  
        self.bot = bot      
        self.detect40x = False     
        self.detect503 = False     
        self.userQuit = False
        self.mode = None        
        self.logger = logging.getLogger(self.bot.botId if self.bot.botId is not None else "unknown")
        self.msgMap = {}    
        self.loginEvent = threading.Event()        
        self.cmdEventMap = {} 
        self.lastOnlineTimeStamp = None
        self.pingCount = 0             
        self.ctxMap = {}
                
    def quit(self):
        self.userQuit = True
        self.onDisconnected(YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT))   

    def setCmdEvent(self,iqid,event):
        self.cmdEventMap[iqid] = {"event":event,"result":"None"}

    def getCmdResult(self,iqid,timeout):        
        if iqid in self.cmdEventMap:
            obj =self.cmdEventMap[iqid]
            if obj["event"].wait(timeout):
                del self.cmdEventMap[iqid]
                if "error" not in obj :
                    return "",obj["result"],False
                else:
                    if obj["error"]=="redirect":
                        return obj["error"],obj["result"],False
                    else:
                        return obj["error"],"",False
            else:
                self.cmdEventMap[iqid]
                #timeout
                return None,None,True                
        else:
            return "404",None,False
        
    def setMsgMap(self,taskId,targets,msgId):
        if taskId is not None:
            array = targets.split(",")
            for target in array:
                self.msgMap[taskId+"-"+target] = msgId

    def getMsgIdFromMsgMap(self,taskId,target):
        if taskId is None:
            return None        
        if (taskId+"-"+target) in self.msgMap:
            return  self.msgMap[taskId+"-"+target]
        return None

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
        profile.write_config(config)

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

    @EventCallback(YowNetworkLayer.EVENT_STATE_DISCONNECTED)
    def onDisconnected(self, yowLayerEvent):             
        self.logger.info("Disconnect")       
        error = self.getStack().getProp("exception")                
        if self.getProp("jid") is not None:            
            self._qrThread.stop()
            waNum,a,deviceid = WATools.jidDecode(self.getProp("jid"))
            self.logger.info("Companion device register sucess(%s_%d)" % (waNum,deviceid))        
            self.setProp("jid",None)
            time.sleep(5)                                       
            self.getStack().setProfile(SysVar.ACCOUNT_PATH+waNum+"_"+str(deviceid))                       
            self.getStack().broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECT))
            return        
        if self.getProp("refs") is not None and len(self.getProp("refs"))==0:            
            time.sleep(5)
            self.getStack().broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECT))
            return

        if self.isConnected:     
            self.eventCallback(wsend_pb2.BotEvent.Event.LOGOUT)

        self.isConnected = False        
    
        if (not self.detect40x) and (not self.userQuit):      
            self.bot.wa_old = None               
            self.loginEvent.clear()
            time.sleep(1)
            self.getStack().broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECT))  
        else:     

            if not self.getProp("HC_MODE"):                                
                self.eventCallback(wsend_pb2.BotEvent.Event.QUIT)                
                if self.userQuit :                
                    Utils.exit(0)    
                else:            
                    Utils.exit(1)         
            else:                
                time.sleep(1)        

    
    @ProtocolEntityCallback("notification")
    def onNotification(self,entity):        

        if isinstance(entity,MexUpdateNotificationProtocolEntity):            
            self.logger.info("Notification: Received a MexUpdate Notification: %s" % entity.jsonObj)            
            return
                    
        if isinstance(entity,CreateGroupsNotificationProtocolEntity):
            self.logger.info("Notification: Group %s created" % entity.groupId)
            return 
        
        if isinstance(entity,AddGroupsNotificationProtocolEntity):
            n = wsend_pb2.Notification()
            n.id = entity.getId()                               
            n.type = wsend_pb2.Notification.Type.Value("GROUP")
            n.sender = entity.getGroupId()
            n.target = self.bot.botId
            n.group_notification.action = wsend_pb2.Notification.GroupNotification.Action.Value("ADD")
            n.group_notification.reason = "invite"            
            n.group_notification.jids.extend(entity.getParticipants())                   
            self.logger.info("Notification: Group %s add participant %s" % (n.sender,entity.getParticipants()[0]))
            return
        
        if isinstance(entity,RemoveGroupsNotificationProtocolEntity):
            n = wsend_pb2.Notification()
            n.id = entity.getId()       
            n.sender = entity.getGroupId()
            n.target = self.bot.botId                                    
            n.type = wsend_pb2.Notification.Type.Value("GROUP")
            n.group_notification.action = wsend_pb2.Notification.GroupNotification.Action.Value("REMOVE")                  
            n.group_notification.jids.extend(entity.getParticipants())                 
            self.logger.info("Notification: Group %s remove participant %s" % (n.sender,entity.getParticipants()[0]))       
            return    
        
        if isinstance(entity,SetPictureNotificationProtocolEntity):
            if entity.setJid is not None:
                self.eventCallback(wsend_pb2.BotEvent.Event.CONTACT_UPDATE,contactUpdate={"target":entity.setJid.split("@")[0],"key":"AVATAR","value":entity.setId})
            return 
        
        if isinstance(entity,BusinessNameUpdateNotificationProtocolEntity):
            if entity.name is not None:
                self.eventCallback(wsend_pb2.BotEvent.Event.CONTACT_UPDATE,contactUpdate={"target":entity.jid.split("@")[0],"key":"NAME","value":entity.name})
            return 
        
        if isinstance(entity,BusinessRemoveNotificationProtocolEntity):
            if entity.jid is not None:
                self.eventCallback(wsend_pb2.BotEvent.Event.CONTACT_UPDATE,contactUpdate={"target":entity.jid.split("@")[0],"key":"REMOVE","value":"True"})
            return         
        
        if isinstance(entity,DisapperingModeNotificationProtocolEntity):
            self.eventCallback(wsend_pb2.BotEvent.Event.CONTACT_UPDATE,contactUpdate={"target":entity._from.split("@")[0],"key":"DISAPPEARING_MODE_DURATION","value":entity.duration})

                                
    def setCmdRedirect(self,cmdId,cmdName,cmdParams,options,context):        
        if cmdId in self.cmdEventMap: 
            obj = self.cmdEventMap[cmdId]
            obj["error"] = "redirect"
            obj["result"] = {
                "cmdName":cmdName,
                "cmdParams":cmdParams,
                "options":options,
                "context":context
            }
            obj["event"].set()

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
    def onIq(self, entity):          
                        
        if isinstance(entity,ResultIqProtocolEntity):
            self.setCmdResult(entity.getId(),{"status":"ok"})
            return 
        
        if isinstance(entity,ErrorIqProtocolEntity):
            self.setCmdError(entity.getId(),entity.code)
            return 
                        
        if isinstance(entity,ResultGetKeysIqProtocolEntity):                  
            return
                 
        if isinstance(entity, MultiDevicePairIqProtocolEntity):                              
            ack = IqProtocolEntity(to = YowConstants.WHATSAPP_SERVER,_type="result",_id=entity.getId())       
            self._sendIq(ack)     
            self.setProp("refs",entity.refs)            
            self._qrThread = YowQrCodeThread(self, 20)            
            self._qrThread.start()
            return 

        if isinstance(entity, MultiDevicePairSuccessIqProtocolEntity):                               
            jid = entity.jid
            self.setProp("refs",None)          
            self.setProp("jid",jid)     
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
            p4.account_signature = p2.account_signature
            p4.details = p2.details
            p4.device_signature = devicesign
            signEntity = MultiDevicePairSignIqProtocolEntity(entity.getId(),p3.key_index,p4.SerializeToString())       
            self._sendIq(signEntity)     
            #保存签名，后续发送消息的时候有用            
            self.genProfile(p4) 
            return 
    
        if isinstance(entity,ResultSetPictureIqProtocolEntity):             
            self.setCmdResult(entity.getId(),{"pictureId":entity.getPictureId()})
            return 
                            
    @ProtocolEntityCallback("failure")
    def onFailure(self, entity):
        self.logger.info("Login Fail")     

        print(entity)
        if entity.reason=="403" or entity.reason=="401" or entity.reason=="405" or entity.reason=="404":
            self.eventCallback(wsend_pb2.BotEvent.Event.LOGIN_FAIL,eventDetail=entity.reason)
            self.detect40x = True            

            if entity.reason!="405" and self.bot.bot_type!=YowBotType.TYPE_RUN_TEMP:
                pass                

            self.loginEvent.set()




    def eventCallback(self,event,eventDetail=None,msgLog=None,contactUpdate=None):        
        if self.bot.callback is not None and self.bot.botId is not None:
            
            e = wsend_pb2.BotEvent()            
            e.bot_id = self.bot.botId
            e.event = event
            if eventDetail is not None:
                e.event_detail = eventDetail

            if msgLog is not None:                
                e.msg_log.msg_id = msgLog["msgId"]
                if "taskId" in msgLog and msgLog["taskId"] is not None:
                    e.msg_log.task_id = msgLog["taskId"] 
                if "sender" in msgLog and msgLog["sender"] is not None:
                    e.msg_log.sender = msgLog["sender"]
                if "status" in msgLog and msgLog["status"] is not None:
                    e.msg_log.status = msgLog["status"] 
                if "target" in msgLog and msgLog["target"] is not None:
                    e.msg_log.target = msgLog["target"] 
                if "errorCode" in msgLog and msgLog["errorCode"] is not None:
                    e.msg_log.error_code = msgLog["errorCode"]
                if "content" in msgLog and msgLog["content"] is not None:
                    e.msg_log.content = msgLog["content"]  

            if contactUpdate is not None:
                if "target" in contactUpdate and contactUpdate["target"] is not None:
                    e.contact_update.target = contactUpdate["target"]
                if "key" in contactUpdate and contactUpdate["key"] is not None:
                    e.contact_update.key = contactUpdate["key"]
                if "value" in contactUpdate and contactUpdate["value"] is not None:
                    e.contact_update.value = contactUpdate["value"]

            e.timestamp = int(time.time())
            self.bot.callback(event = e,logger =self.logger,caller=self.bot)


    def messageCallback(self,msg):
        #if msg.HasField("participant"):
            #group msg, ignore it
        #    return
        if self.bot.callback is not None:
            msg.bot_id = self.bot.botId
            self.bot.callback(message=msg,logger=self.logger,caller=self.bot)

    @ProtocolEntityCallback("success")
    def onSuccess(self, successProtocolEntity):                  
        self.logger.info("Login OK")     
                            
        self.isConnected = True
        self.loginEvent.set()  
        entity = AvailablePresenceProtocolEntity()
        self.toLower(entity)                
   
        self.eventCallback(wsend_pb2.BotEvent.Event.LOGIN_SUCCESS)
        
        self.lastOnlineTimeStamp = int(time.time()) 

        #self.setProp(PROP_IDENTITY_AUTOTRUST, True)
        

    @ProtocolEntityCallback("stream:error")
    def onStreamError(self, entity):
        self.logger.info("Stream Error")      
        print(entity)        

        if entity.code is not None :
            if entity.code=="503":
                self.detect503 = True      
                self.bot._stack.broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT))                
   
    @ProtocolEntityCallback("ack")
    def onAck(self, entity):                
        
        if entity.getId() in self.ackQueue:

            if entity._from is not None:
                num = entity._from[0:entity._from.rfind('@', 0)]                  

            if entity.getError() is None:                                                      
                    self.eventCallback(wsend_pb2.BotEvent.Event.MSG_LOG,msgLog={
                            'msgId':entity.getId(),                                                 
                            'sender':self.bot.botId,
                            'target':num,
                            'status': wsend_pb2.MsgLogItem.Status.Value("SENT")
                    })
            else:   

                    pass                    
                    self.eventCallback(wsend_pb2.BotEvent.Event.MSG_LOG,msgLog={
                            'msgId':entity.getId(),                            
                            'sender':self.bot.botId,
                            'target':num,
                            'errorCode': entity.getError(),
                            'status': wsend_pb2.MsgLogItem.Status.Value("ERROR")
                    })                                    
            
                                
            self.ackQueue.pop(self.ackQueue.index(entity.getId()))            
               
    def download(self,params):
                    
        enc_data = requests.get(url=params["url"]).content

        if enc_data is None:            
            logger.error("Download failed")        
            return None
        
        filename = params["filename"]
        ext = None


        if params["type"]=="IMAGE":
            media_info = MediaCipher.INFO_IMAGE            
        elif params["type"]=="VIDEO":
            media_info = MediaCipher.INFO_VIDEO    
        elif params["type"]=="AUDIO":
            media_info = MediaCipher.INFO_AUDIO
        elif params["type"]=="DOCUMENT":
            media_info = MediaCipher.INFO_DOCUMENT
        elif params["type"]=="STICKER":
            media_info = MediaCipher.INFO_IMAGE
        else:
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
    


    @ProtocolEntityCallback("message")
    def onMessage(self, messageProtocolEntity):            
        
        if messageProtocolEntity.getParticipant() is not None:
            _from = messageProtocolEntity.getFrom(False)+"::"+messageProtocolEntity.getParticipant(False)
        else:
            _from = messageProtocolEntity.getFrom(False)
        
        if messageProtocolEntity.getType() == 'text' :

            type = "text"
            if isinstance(messageProtocolEntity, TextMessageProtocolEntity):                                                            
                text = messageProtocolEntity.getBody()     
            if isinstance(messageProtocolEntity, ExtendedTextMessageProtocolEntity):                                           
                text = messageProtocolEntity.text          
                if messageProtocolEntity.context_info is not None and messageProtocolEntity.context_info.external_ad_reply is not None:
                    type="ad"

            msg = wsend_pb2.Message()                         
            msg.msg_id = messageProtocolEntity.getId()                            
            msg.target = messageProtocolEntity.getTo(False) if messageProtocolEntity.fromme else self.bot.botId
            msg.sender = messageProtocolEntity.getFrom(False)
            msg.notify = messageProtocolEntity.getNotify()
            msg.timestamp = int(time.time())
            if messageProtocolEntity.getParticipant(False) :
                msg.participant = messageProtocolEntity.getParticipant(False) 

            if type=="text":
                msg.type = wsend_pb2.Message.Type.Value("TEXT")  
                msg.text_message.text = text                   

            if type=="ad":
                msg.type = wsend_pb2.Message.Type.Value("AD")
                msg.ad_message.text = text
                msg.ad_message.title = messageProtocolEntity.context_info.external_ad_reply.title
                msg.ad_message.thumbnail = messageProtocolEntity.context_info.external_ad_reply.thumbnail
                msg.ad_message.url = messageProtocolEntity.context_info.external_ad_reply.source_url
                msg.ad_message.larger_thumbnail = messageProtocolEntity.context_info.external_ad_reply.render_larger_thumbnail

            
            self.messageCallback(msg)

                 

        elif messageProtocolEntity.getType() == 'media':  

            msg = wsend_pb2.Message()                                
            msg.msg_id = messageProtocolEntity.getId()                
            msg.target = messageProtocolEntity.getTo(False) if messageProtocolEntity.fromme else self.bot.botId
            msg.sender = messageProtocolEntity.getFrom(False)
            msg.notify = messageProtocolEntity.getNotify()
            if messageProtocolEntity.getParticipant(False) :
                msg.participant = messageProtocolEntity.getParticipant(False) 

            msg.timestamp = int(time.time())
            if isinstance(messageProtocolEntity,ExtendedTextMediaMessageProtocolEntity):        
       
                type="url"
                if messageProtocolEntity.media_specific_attributes.context_info is not None and messageProtocolEntity.media_specific_attributes.context_info.external_ad_reply is not None:
                    type="ad"

                msg = wsend_pb2.Message()                         
                msg.msg_id = messageProtocolEntity.getId()                            
                msg.target = messageProtocolEntity.getTo(False) if messageProtocolEntity.fromme else self.bot.botId
                msg.sender = messageProtocolEntity.getFrom(False)
                msg.notify = messageProtocolEntity.getNotify()
                msg.timestamp = int(time.time())
                if messageProtocolEntity.getParticipant(False) :
                    msg.participant = messageProtocolEntity.getParticipant(False) 

                if type=="ad":
                    msg.type = wsend_pb2.Message.Type.Value("AD")
                    msg.ad_message.text = messageProtocolEntity.text
                    msg.ad_message.title = messageProtocolEntity.media_specific_attributes.context_info.external_ad_reply.title
                    msg.ad_message.thumbnail = messageProtocolEntity.media_specific_attributes.context_info.external_ad_reply.thumbnail
                    msg.ad_message.url = messageProtocolEntity.media_specific_attributes.context_info.external_ad_reply.source_url
                    msg.ad_message.larger_thumbnail = messageProtocolEntity.media_specific_attributes.context_info.external_ad_reply.render_larger_thumbnail
                else :
                    msg.type = wsend_pb2.Message.Type.Value("URL")                
                    msg.url_message.text = messageProtocolEntity.text   
                    msg.url_message.url  = messageProtocolEntity.matched_text
                          
                self.messageCallback(msg)                
                    
                               
            elif isinstance(messageProtocolEntity,ImageDownloadableMediaMessageProtocolEntity):
                text = "[image]"                      
                msg.type = wsend_pb2.Message.Type.Value("IMAGE") 
                msg.image_message.url = messageProtocolEntity.downloadablemedia_specific_attributes.url
                msg.image_message.mimetype = messageProtocolEntity.downloadablemedia_specific_attributes.mimetype
                if  messageProtocolEntity.caption:
                    msg.image_message.caption = messageProtocolEntity.caption 
                msg.image_message.file_sha256 = messageProtocolEntity.downloadablemedia_specific_attributes.file_sha256
                msg.image_message.file_length = messageProtocolEntity.downloadablemedia_specific_attributes.file_length
                msg.image_message.height = messageProtocolEntity.height
                msg.image_message.width  = messageProtocolEntity.width
                msg.image_message.media_key = messageProtocolEntity.downloadablemedia_specific_attributes.media_key
                msg.image_message.file_enc_sha256 = messageProtocolEntity.downloadablemedia_specific_attributes.file_enc_sha256
                msg.image_message.direct_path = messageProtocolEntity.downloadablemedia_specific_attributes.direct_path
                msg.image_message.media_key_timestamp = messageProtocolEntity.downloadablemedia_specific_attributes.media_key_timestamp
                if  messageProtocolEntity.jpeg_thumbnail:
                    msg.image_message.jpeg_thumbnail = messageProtocolEntity.jpeg_thumbnail
                self.messageCallback(msg)                             

            elif isinstance(messageProtocolEntity,VideoDownloadableMediaMessageProtocolEntity):
                text = "[video]"      
                msg.type = wsend_pb2.Message.Type.Value("VIDEO") 
                msg.video_message.url = messageProtocolEntity.downloadablemedia_specific_attributes.url
                msg.video_message.mimetype = messageProtocolEntity.downloadablemedia_specific_attributes.mimetype
                if  messageProtocolEntity.caption:
                    msg.video_message.caption = messageProtocolEntity.caption 
                msg.video_message.file_sha256 = messageProtocolEntity.downloadablemedia_specific_attributes.file_sha256
                msg.video_message.file_length = messageProtocolEntity.downloadablemedia_specific_attributes.file_length
                msg.video_message.height = messageProtocolEntity.height
                msg.video_message.width  = messageProtocolEntity.width
                msg.video_message.seconds= messageProtocolEntity.seconds
                msg.video_message.gif_playback = messageProtocolEntity.gif_playback
                msg.video_message.media_key = messageProtocolEntity.downloadablemedia_specific_attributes.media_key
                msg.video_message.file_enc_sha256 = messageProtocolEntity.downloadablemedia_specific_attributes.file_enc_sha256
                msg.video_message.direct_path = messageProtocolEntity.downloadablemedia_specific_attributes.direct_path
                msg.video_message.media_key_timestamp = messageProtocolEntity.downloadablemedia_specific_attributes.media_key_timestamp
                msg.video_message.jpeg_thumbnail = messageProtocolEntity.jpeg_thumbnail
                self.messageCallback(msg)   

            elif isinstance(messageProtocolEntity,AudioDownloadableMediaMessageProtocolEntity):
                text = "[audio]"      
                msg.type = wsend_pb2.Message.Type.Value("AUDIO") 
                msg.audio_message.url = messageProtocolEntity.downloadablemedia_specific_attributes.url
                msg.audio_message.mimetype = messageProtocolEntity.downloadablemedia_specific_attributes.mimetype
                msg.audio_message.file_sha256 = messageProtocolEntity.downloadablemedia_specific_attributes.file_sha256
                msg.audio_message.file_length = messageProtocolEntity.downloadablemedia_specific_attributes.file_length
                msg.audio_message.seconds= messageProtocolEntity.seconds
                msg.audio_message.ptt = messageProtocolEntity.ptt
                msg.audio_message.media_key = messageProtocolEntity.downloadablemedia_specific_attributes.media_key
                msg.audio_message.file_enc_sha256 = messageProtocolEntity.downloadablemedia_specific_attributes.file_enc_sha256
                msg.audio_message.direct_path = messageProtocolEntity.downloadablemedia_specific_attributes.direct_path
                msg.audio_message.media_key_timestamp = messageProtocolEntity.downloadablemedia_specific_attributes.media_key_timestamp                

                self.messageCallback(msg)     

            elif isinstance(messageProtocolEntity,DocumentDownloadableMediaMessageProtocolEntity):
                text = "[document]"
                msg.type = wsend_pb2.Message.Type.Value("DOCUMENT")                 

                if messageProtocolEntity.downloadablemedia_specific_attributes:                    
                    msg.document_message.url = messageProtocolEntity.downloadablemedia_specific_attributes.url
                    msg.document_message.mimetype = messageProtocolEntity.downloadablemedia_specific_attributes.mimetype                                    
                    if  messageProtocolEntity.caption:
                        msg.document_message.caption = messageProtocolEntity.caption                 

                    if messageProtocolEntity.title:
                        msg.document_message.title = messageProtocolEntity.title
                    msg.document_message.file_sha256 = messageProtocolEntity.downloadablemedia_specific_attributes.file_sha256
                    msg.document_message.file_length = messageProtocolEntity.downloadablemedia_specific_attributes.file_length

                    if messageProtocolEntity.page_count:
                        msg.document_message.page_count= messageProtocolEntity.page_count
                    msg.document_message.file_name = messageProtocolEntity.file_name
                    msg.document_message.media_key = messageProtocolEntity.downloadablemedia_specific_attributes.media_key
                    msg.document_message.file_enc_sha256 = messageProtocolEntity.downloadablemedia_specific_attributes.file_enc_sha256
                    msg.document_message.direct_path = messageProtocolEntity.downloadablemedia_specific_attributes.direct_path
                    msg.document_message.media_key_timestamp = messageProtocolEntity.downloadablemedia_specific_attributes.media_key_timestamp                                            

                    self.messageCallback(msg)   

            elif  isinstance(messageProtocolEntity,StickerDownloadableMediaMessageProtocolEntity):
                text = "[sticker]"
                msg.type = wsend_pb2.Message.Type.Value("STICKER")                 
                if messageProtocolEntity.downloadablemedia_specific_attributes:                    
                    msg.sticker_message.url = messageProtocolEntity.downloadablemedia_specific_attributes.url
                    msg.sticker_message.mimetype = messageProtocolEntity.downloadablemedia_specific_attributes.mimetype                                    
                    msg.sticker_message.file_sha256 = messageProtocolEntity.downloadablemedia_specific_attributes.file_sha256
                    msg.sticker_message.file_length = messageProtocolEntity.downloadablemedia_specific_attributes.file_length

                    msg.sticker_message.height = messageProtocolEntity.height
                    msg.sticker_message.width  = messageProtocolEntity.width
                    
                    msg.sticker_message.media_key = messageProtocolEntity.downloadablemedia_specific_attributes.media_key
                    msg.sticker_message.file_enc_sha256 = messageProtocolEntity.downloadablemedia_specific_attributes.file_enc_sha256
                    msg.sticker_message.direct_path = messageProtocolEntity.downloadablemedia_specific_attributes.direct_path
                    msg.sticker_message.media_key_timestamp = messageProtocolEntity.downloadablemedia_specific_attributes.media_key_timestamp           

                    msg.sticker_message.is_animated = messageProtocolEntity.is_animated                    
                    msg.sticker_message.sticker_sent_ts = messageProtocolEntity.sticker_sent_ts
                    msg.sticker_message.is_avatar = messageProtocolEntity.is_avatar
                    msg.sticker_message.is_ai_sticker = messageProtocolEntity.is_ai_sticker
                    msg.sticker_message.is_lottie = messageProtocolEntity.is_lottie
                    self.messageCallback(msg)   
            else:          
                text = "[media]" 
                msg.type = wsend_pb2.Message.Type.Value("OTHER") 
                self.messageCallback(msg)
                                

      
        self.toLower(messageProtocolEntity.ack())
        self.toLower(messageProtocolEntity.ack(True))
                                  


    @ProtocolEntityCallback("receipt")
    def onReceipt(self, entity):

        if entity.getParticipant() is not None:
            _from = entity.getFrom(False)+"::"+entity.getParticipant(False)
        else:
            _from = entity.getFrom(False)
            
        #群发模式，有待跟踪的消息id                          
        if entity.getType() == "read":
            self.eventCallback(wsend_pb2.BotEvent.Event.MSG_LOG,msgLog={
                'msgId':entity.getId(),
                'sender':self.bot.botId,
                'target':_from,
                'status': wsend_pb2.MsgLogItem.Status.Value("READ")                

            })                                             
        else:
            self.eventCallback(wsend_pb2.BotEvent.Event.MSG_LOG,msgLog={
                'msgId':entity.getId(),                
                'sender':self.bot.botId,
                'target':_from,                          
                'status': wsend_pb2.MsgLogItem.Status.Value("RECEIVED")
            }) 

        self.toLower(entity.ack())        

    def isConnected(self):
       return self.isConnected
                      
    def waitLogin(self):
        #等待bot连接就绪,
        #超时返回false，正常登录返回true        
        return self.loginEvent.wait(20)
    

    def multiSend(self,cmdParams,options):
        tos, *other = cmdParams
        toArr = tos.split(",")
        if len(toArr)==0:
            self.logger.info("No target to send")
            return False

        repeat = int(Utils.getOption(options,"repeat",1))
        execCount = 0
        for i in range(0,repeat):
            for to in toArr:            
                params = [to]
                params.extend(cmdParams[1:])
                self.sendMsg(params,options)
                execCount+= 1
                time.sleep(3)
                            
        return "JUSTWAIT"

    
    def assureContactsAndSend(self,cmdParams,options,send_func,redo_func):        
        to,message,*other = cmdParams

        isCompanion = "_" in self.bot.botId

        newContacts = self.db._store.findNewContacts(Jid.normalize(to))        
        if len(newContacts)>0 and not isCompanion:
            self.db._store.addContacts(newContacts) 
            entity = GetSyncIqProtocolEntity(numbers=newContacts,mode = "delta")    
            def on_success(entity, original_iq_entity):  
                #同步成功,重新调用一次
                logger.info("add target(s) to contacts")      
                redo_func(cmdParams,options)                
            def on_error(entity, original_iq):         
                print("ERROR")   

            self._sendIq(entity,on_success,on_error)                        
        else:
            if not isCompanion:
                logger.info("target(s) in contacts ")       
            else:
                logger.info("companion send ")       

            send_func(cmdParams,options)        
            return False    

    def sendMsgDirect(self,cmdParams,options):
        to,message,*other = cmdParams
        context_info = ContextInfoAttributes()

        if "source" in options:
            if options["source"]=="random":
                srcs = ["contact_card","contact_search","global_search_new_chat","phone_number_hyperlink"]
                source = random.choice(srcs)
            else:
                #"group_participant_list"
                source = options["source"]

            context_info.entry_point_conversion_app ="whatsapp"
            context_info.entry_point_conversion_source = source
            context_info.entry_point_conversion_delay_seconds = random.randint(5,13)

        if "url" in options:
            url = options["url"]                    
            urlTitle = options["urltitle"] if "urltitle" in options else None
            urlDesc = options["urldesc"] if "urldesc" in options else None
            
            attr = ExtendedTextAttributes(
                text = message,            
                matched_text = url,
                description= urlDesc,
                title = urlTitle,
                context_info= context_info
            )     
        elif "bjid" in options:
            context_info.forwarding_score=2
            context_info.is_forwarded=True
            context_info.business_message_forward_info=BusinessMessageForwardInfoAttributes(
                        business_owner_jid=Jid.normalize(options["bjid"])
                    )              
            attr = ExtendedTextAttributes(
                text = message,
                preview_type=0,
                context_info= context_info,
                invite_link_group_type_v2=0
            )   
        else:        
            attr = ExtendedTextAttributes(                
                text = message,
                preview_type=0,
                context_info= context_info,
                invite_link_group_type_v2=0
            )            

        messageEntity = ExtendedTextMessageProtocolEntity(attr, 
            MessageMetaAttributes(id=self.bot.idType,recipient=Jid.normalize(to),timestamp=int(time.time()))            
        )        


        self.ackQueue.append(messageEntity.getId())
        self.logger.info("Send Msg (ID=%s)" % messageEntity.getId())

        target = Jid.normalize(to.split(",")[0])
        if target.endswith("@g.us"):
            entity = OutgoingChatstateProtocolEntity(ChatstateProtocolEntity.STATE_TYPING, target,Jid.normalize(self.bot.botId))
        else:
            entity = OutgoingChatstateProtocolEntity(ChatstateProtocolEntity.STATE_TYPING, target)

        self.toLower(entity)
        time.sleep(1)
        self.toLower(messageEntity)   

        self.eventCallback(wsend_pb2.BotEvent.Event.MSG_LOG,msgLog={
                'msgId':messageEntity.getId(),                
                'sender':self.bot.botId,
                "target":to[0:Jid.normalize(to).rfind("@",0)],                
                'status': wsend_pb2.MsgLogItem.Status.Value("EXECUTED")                
            })      
        
        if "waitMsgId" in options:
            self.ctxMap[options["ctxId"]]["msgId"] = messageEntity.getId()
            self.ctxMap[options["ctxId"]]["event"].set()            
        
        return messageEntity.getId()        
    
    def getContextValue(self,ctxId,key):
        if ctxId not in self.ctxMap:
            return None        
        if key not in self.ctxMap[ctxId]:
            return None        
        return self.ctxMap[ctxId][key]
    
    def sendMsg(self,cmdParams,options):        

        if "waitMsgId" not in options:
            self.assureContactsAndSend(cmdParams,options,send_func=self.sendMsgDirect,redo_func=self.sendMsg)            
            return "JUSTWAIT"
        else:
            ctxId = str(uuid.uuid4())            
            self.ctxMap[ctxId] = {"event":threading.Event()}
            options["ctxId"] = ctxId                        
            print(ctxId)
            self.assureContactsAndSend(cmdParams,options,send_func=self.sendMsgDirect,redo_func=self.sendMsg)            
            #等待消息ID的返回
            ret = self.ctxMap[ctxId]["event"].wait(int(options["waitMsgId"]))
            if not ret:
                return "TIMEOUT"
            else:
                msgId = self.getContextValue(ctxId,"msgId")
                del self.ctxMap[ctxId]
                return msgId

    def sendMediaMsg(self,cmdParams,options):
    
        if "waitMsgId" not in options:
            self.assureContactsAndSend(cmdParams,options,send_func=self.sendMediaMsgDirect,redo_func=self.sendMediaMsg)            
            return "JUSTWAIT"             
        else:
            ctxId = str(uuid.uuid4())            
            self.ctxMap[ctxId] = {"event":threading.Event()}
            options["ctxId"] = ctxId                        
            self.assureContactsAndSend(cmdParams,options,send_func=self.sendMediaMsgDirect,redo_func=self.sendMediaMsg)                        
                 
            ret = self.ctxMap[ctxId]["event"].wait(int(options["waitMsgId"]))            
            if not ret:                
                return "TIMEOUT"
            else:                
                msgId = self.getContextValue(ctxId,"msgId")
                del self.ctxMap[ctxId]
                return msgId
            
    def sendMediaMsgDirect(self,cmdParams,options):
        def onRequestMediaConnResult(cmdParams, resultRequestMediaConnIqProtocolEntity, requestMediaConnIqProtocolEntity):
            to, mediaType, filePath,*other = cmdParams    
            caption = options["caption"] if "caption" in options else None
            fileName = options["fileName"] if "fileName" in options else None

            try:
                if mediaType=="image":
                    if filePath.startswith("http://") or filePath.startswith("https://"):
                        attr_media = ImageAttributes.from_url(filePath,mediaType,resultRequestMediaConnIqProtocolEntity)
                    else:
                        attr_media = ImageAttributes.from_filepath(filePath,mediaType,resultRequestMediaConnIqProtocolEntity)
                    attr_media.caption = caption
                    
                    entity = ImageDownloadableMediaMessageProtocolEntity(
                        image_attrs=attr_media,
                        message_meta_attrs=MessageMetaAttributes(id=self.bot.idType,recipient=Jid.normalize(to))
                    )            

                if mediaType=="video":            
                    if filePath.startswith("http://") or filePath.startswith("https://"):
                        attr_media = VideoAttributes.from_url(filePath,mediaType,resultRequestMediaConnIqProtocolEntity)
                    else:
                        attr_media = VideoAttributes.from_filepath(filePath,mediaType,resultRequestMediaConnIqProtocolEntity)
                    attr_media.caption = caption            
                    entity = VideoDownloadableMediaMessageProtocolEntity(
                        video_attrs=attr_media,
                        message_meta_attrs=MessageMetaAttributes(id=self.bot.idType,recipient= Jid.normalize(to))
                    )                         

                if mediaType=="audio":      
                    if filePath.startswith("http://") or filePath.startswith("https://"):
                        attr_media = AudioAttributes.from_url(filePath,mediaType,resultRequestMediaConnIqProtocolEntity)          
                    else:      
                        attr_media = AudioAttributes.from_filepath(filePath,mediaType,resultRequestMediaConnIqProtocolEntity)          
                    entity = AudioDownloadableMediaMessageProtocolEntity(
                        audio_attrs=attr_media,
                        message_meta_attrs=MessageMetaAttributes(id=self.bot.idType,recipient= Jid.normalize(to))
                    )                         
                    
                if mediaType=="document":        
                    if filePath.startswith("http://") or filePath.startswith("https://"):
                        attr_media = DocumentAttributes.from_url(filePath,fileName,mediaType,resultRequestMediaConnIqProtocolEntity)  
                    else:
                        attr_media = DocumentAttributes.from_filepath(filePath,fileName,mediaType,resultRequestMediaConnIqProtocolEntity)          
                    entity = DocumentDownloadableMediaMessageProtocolEntity(
                        document_attrs=attr_media,
                        message_meta_attrs=MessageMetaAttributes(id=self.bot.idType,recipient= Jid.normalize(to))
                    )                                    

                self.logger.info("Send Media %s Msg (ID=%s)" % (mediaType,entity.getId()))                

                self.ackQueue.append(entity.getId())

                self.toLower(entity) 

                self.eventCallback(wsend_pb2.BotEvent.Event.MSG_LOG,msgLog={
                    'msgId':entity.getId(),                    
                    'sender':self.bot.botId,
                    "target":to[0:Jid.normalize(to).rfind("@",0)],
                    'status': wsend_pb2.MsgLogItem.Status.Value("EXECUTED")                
                })  

                if "waitMsgId" in options:
                    self.ctxMap[options["ctxId"]]["msgId"] = entity.getId()
                    self.ctxMap[options["ctxId"]]["event"].set()            

                return entity.getId()                   
            except:
                print(traceback.format_exc())
                logger.error("send media msg with exception")
                return None
                
        def onRequestMediaConnError(cmdParams, errorRequestUploadIqProtocolEntity, requestUploadIqProtocolEntity):
            logger.error("Request upload for file failed")

        mediaType = cmdParams[1]
        if not mediaType in ["image","video","audio","document"]:
            self.logger.info("sendmedia type %s is not supported now" % mediaType)

        entity = RequestMediaConnIqProtocolEntity()
        successFn = lambda successEntity, originalEntity: onRequestMediaConnResult( cmdParams, successEntity, originalEntity)
        errorFn = lambda errorEntity, originalEntity: onRequestMediaConnError(cmdParams, errorEntity, originalEntity)
        self._sendIq(entity, successFn, errorFn)

    def syncContacts(self,cmdParams,options):            
        if "mode" not in options:
            options["mode"] = "delta"                      
        if "cnt" not in options:
            options["cnt"] = "30"

        nums = cmdParams[0].split(',')        
      
        entity = GetSyncIqProtocolEntity(nums,mode = options["mode"])    

        def on_success(entity, original_iq_entity):  
            self.logger.info("syncContacts success with %d contacts" % len(entity.inNumbers))                      
            self.setCmdResult(entity.getId(),{
                "count": len(entity.inNumbers),
                "jids": list(entity.inNumbers.values())
            })               

        def on_error(entity, original_iq):            
            self.logger.error("syncContacts error")
            

        self._sendIq(entity,on_success,on_error)
        return entity.getId()
 
    def getConfig(self,cmdParams,options)  :
        push = PushIqProtocolEntity()
        self.toLower(push)
        self.logger.info("push iq")
        props = PropsIqProtocolEntity()
        self.toLower(props)
        self.logger.info("props iq")

    def cleanDirty(self,cmdParams,options) :
        entity = CleanDirtyIqProtocolEntity(type=cmdParams[0])
        self.toLower(entity)

    def joinGroupWithCode(self,cmdParams,options):        

        def on_success(entity, original_iq_entity):                 
            self.logger.info("joinGroupWithCode success")    
            self.setCmdResult(entity.getId(),{"group_jid":entity.groupId})
                                                 
        def on_fail(entity, original_iq):          
            self.logger.error("joinGroupWithCode error")         


        entity = JoinWithCodeGroupsIqProtocolEntity(code=cmdParams[0])

        self._sendIq(entity,on_success,on_fail)
        return entity.getId()        


    def getAvatar(self,cmdParams,options):        
        if len(cmdParams)==0:
            target = self.bot.botId
        else:
            target = cmdParams[0]

        def on_success(entity, original_iq_entity):                   
            result = {
                "id":entity.getPictureId(),
                "type":entity.getPictureType(),
                "url":entity.getUrl()
            }                
            self.setCmdResult(entity.getId(),result)
            return     

        def on_error(entity, original_iq):                                                 
            self.setCmdError(entity.getId(),entity.code)
        
        entity = GetPictureIqProtocolEntity(jid=Jid.normalize(target),preview=False)        

        self._sendIq(entity,on_success,on_error)
        return entity.getId()
    
    def set2FA(self,cmdParams,options) :
        if len(cmdParams)==0:
            cmdParams = [self.bot_api.botId[-6:], self.bot_api.botId+"@163.com"]
        entity = Set2FAIqProtocolEntity(code=cmdParams[0],email=cmdParams[1])
        self.toLower(entity)        
        return entity.getId()
                
    def setAvatar(self,cmdParams,options):
        if len(cmdParams) > 0:
            url = cmdParams[0]
        else:
            raise ParamsNotEnoughException()            
                
        with PILOptionalModule(failMessage = "No PIL library installed, try install pillow") as imp:
            Image = imp("Image")
            src = Image.open(io.BytesIO(requests.get(url).content)).convert("RGB")
            picture = io.BytesIO()
            preview = io.BytesIO()
            src.resize((640, 640)).save(picture,format="jpeg")
            src.resize((96, 96)).save(preview,format="jpeg")
                                    
            entity = SetPictureIqProtocolEntity("s.whatsapp.net", preview.getvalue(), picture.getvalue())
            self.toLower(entity)            
            return entity.getId()

    def subscribePresence(self, cmdParams,options):
        entity = SubscribePresenceProtocolEntity(jid = Jid.normalize(cmdParams[0]))
        self.toLower(entity)
        return entity.getId()

    def setName(self, cmdParams,options):       
        entity = PresenceProtocolEntity(name = cmdParams[0])
        self.toLower(entity)
        return entity.getId()

    def addTrustedContact(self,cmdParams,options):
        def onSuccess(resultIqEntity, originalIqEntity):
            self.logger.info("setPrivacy Success")

        def onError(errorIqEntity, originalIqEntity):
            self.logger.info("setPrivacy Error")
        
        entity = SetPrivacyIqProtocolEntity(Jid.normalize(cmdParams[0]),int(time.time()))
        self._sendIq(entity, onSuccess, onError)    
    
    def setBusinessName(self,cmdParams,options):     

        def on_success(entity, original_iq_entity):                                 
            self.setCmdResult(entity.getId(),{"status":"OK"})
                            
        def on_error(entity, original_iq):          
            logger.error("listGroup error")            

        #更新profile中的名字
        entity = SetBusinessNameIqProtocolEntity(profile = self.getStack().getProp("profile"), name = cmdParams[0])
        self._sendIq(entity,on_success,on_error)
        return entity.getId()

    def setMode(self,mode):
        self.mode = mode

    def makeGroup(self,params,options):        
        if len(params)!=2:
            self.setCmdResult()
        if params[1]=="":
            self.logger.info("create an empty group")
            pList = None
        else:
            pList = Jid.normalize(params[1]).split(",")
        entity = CreateGroupsIqProtocolEntity(params[0],participants=pList,creator=self.bot.botId)    

        def on_success(entity, original_iq_entity):        
            if isinstance(entity,SuccessCreateGroupsIqProtocolEntity):    
                self.logger.info("makegroup success")                
                self.setCmdResult(entity.getId(),{
                    "groupId":entity.groupId
                })
        def on_error(entity, original_iq):                        
            logger.error("makegroup error")       
         
        self._sendIq(entity,on_success,on_error)
        return entity.getId()

    def groupInfo(self,cmdParams,options):

        def on_success(entity, original_iq_entity):  
            self.logger.info("groupinfo success")            
            self.setCmdResult(entity.getId(),{
                "groupId": entity.groupId,
                "subject": entity.subject,
                "participants": entity.participants
            })                        

        def on_error(entity, original_iq):            
            self.logger.error("groupinfo error")
            self.setCmdError(entity.getId(),entity.code)

        entity = InfoGroupsIqProtocolEntity(group_jid = Jid.normalize(cmdParams[0]))

        self._sendIq(entity,on_success,on_error)

        return entity.getId()


    def getGroupInvite(self,cmdParams,options):

        def on_success(entity, original_iq_entity):            
            if isinstance(entity,SuccessGetInviteCodeGroupsIqProtocolEntity):    
                self.logger.info("getgroupinvite success")       
                self.setCmdResult(entity.getId(), {
                    "groupJid":entity.groupJid,
                    "inviteCode": entity.inviteCode
                })       

        def on_error(entity, original_iq):                        
            self.logger.info("getgroupinvite error")  

        to = cmdParams[0]        
        entity = GetInviteCodeGroupsIqProtocolEntity(group_jid=Jid.normalize(to))
        self._sendIq(entity, on_success, on_error)
        
        return entity.getId()

    def groupAdd(self,cmdParams,options):

        def on_success(entity, original_iq_entity):  
            self.logger.info("groupadd success")

            self.setCmdResult(entity.getId(),{
                "successCount": len(entity.successList),
                "successJids": entity.successList,
                "errorCount": len(entity.errorList),
                "errorJids": entity.errorList
            }) 

        def on_error(entity, original_iq):            
            self.logger.error("groupadd error")
            self.setCmdError(entity.getId(),entity.code)

        entity = AddParticipantsIqProtocolEntity(
            group_jid = Jid.normalize(cmdParams[0]),
            participantList=Jid.normalize(cmdParams[1]).split(",")
        )
        self._sendIq(entity,on_success,on_error)
        return entity.getId()
    
    def groupPromote(self,cmdParams,options):
        entity = PromoteParticipantsIqProtocolEntity(
            group_jid = Jid.normalize(cmdParams[0]),
            participantList=Jid.normalize(cmdParams[1]).split(",")            
        )
        self.toLower(entity)
        return entity.getId()

    def groupDemote(self,cmdParams,options):
        entity = DemoteParticipantsIqProtocolEntity(
            group_jid = Jid.normalize(cmdParams[0]),
            participantList=Jid.normalize(cmdParams[1]).split(",")            
        )
        self.toLower(entity)
        return entity.getId()

    def groupRemove(self,cmdParams,options):
        entity = RemoveParticipantsIqProtocolEntity(
            group_jid = Jid.normalize(cmdParams[0]),
            participantList=Jid.normalize(cmdParams[1]).split(",")            
        )
        self.toLower(entity)
        return entity.getId()

    def groupApprove(self,cmdParams,options):

        if len(cmdParams)>=3:
            action = cmdParams[2]
        else:
            action = 'approve'

        entity = ApproveParticipantsGroupsIqProtocolEntity(
            group_jid = Jid.normalize(cmdParams[0]),
            participantList=Jid.normalize(cmdParams[1]).split(","),
            action = action            
        )        
        self.toLower(entity)

    def setGroupIcon(self,cmdParams,options):
        group_jid = Jid.normalize(cmdParams[0])
        url = cmdParams[1]
        
        with PILOptionalModule(failMessage = "No PIL library installed, try install pillow") as imp:
            Image = imp("Image")

            src = Image.open(io.BytesIO(requests.get(url).content)).convert("RGB")
            picture = io.BytesIO()
            preview = io.BytesIO()
            src.resize((640, 640)).save(picture,format="jpeg")
            src.resize((96, 96)).save(preview,format="jpeg")
                                    
            entity = SetPictureIqProtocolEntity("s.whatsapp.net", preview.getvalue(), picture.getvalue(),target=Jid.normalize(group_jid))   
            self.toLower(entity)
            return entity.getId()        
            
    def leaveGroup(self,cmdParams,options):
        def on_success(entity, original_iq_entity):         
            self.logger.info("leavegroup success")  
            self.setCmdResult(entity.getId(),{"status":"ok"})                                                 
        def on_error(entity, original_iq):          
            self.logger.error("leavegroup error")              

        groupJid = cmdParams[0]        
        entity = LeaveGroupsIqProtocolEntity([Jid.normalize(groupJid)])
        self._sendIq(entity, on_success, on_error)
        return entity.getId()
