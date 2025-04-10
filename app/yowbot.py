import os,sys
sys.path.append(os.getcwd())

# coding=UTF-8
import logging

from yowsup.stacks import YowStackBuilder
from yowsup.layers import YowLayerEvent
from yowsup.layers.network import YowNetworkLayer
from app.yowbot_layer import SendLayer
from conf.constants import SysVar
from yowsup.common.tools import WATools
from axolotl.util.keyhelper import KeyHelper
from yowsup.profile.profile import YowProfile
from proto import wsend_pb2
from common.utils import Utils
from app.bot_env import BotEnv
from app.device_env import DeviceEnv
from app.network_env import NetworkEnv
from app.yowbot_values import YowBotType
from app.param_not_enough_exception import ParamsNotEnoughException
from yowsup.structs import ProtocolEntity
import names

import os,time,threading,uuid,json,inspect,time,socks

logger = logging.getLogger(__name__)

class BotCmd(object):
    def __init__(self, cmd , desc, order = 0):
        self.cmd  = cmd
        self.desc = desc
        self.order = order
    def __call__(self, fn):
        fn.cmd = self.cmd
        fn.desc = self.desc
        fn.order = self.order
        return fn   
        
class YowBot: 
                    
    def __init__(self,bot_id,env,bot_type=YowBotType.TYPE_RUN_MANUAL):     
        self.botId = bot_id                
        stackBuilder = YowStackBuilder()
        self.sendLayer = SendLayer(self)        
        self.env = env if env is not None else BotEnv(deviceEnv=DeviceEnv("android"),networkEnv=NetworkEnv("direct"))

        if self.env.deviceEnv.getOSName() in ["Android","SMBA"]:
            self.idType = ProtocolEntity.ID_TYPE_ANDROID            
        else:
            self.idType = ProtocolEntity.ID_TYPE_IOS
                
        if self.botId is not None:   
            path = SysVar.ACCOUNT_PATH 
            self.profile = YowProfile(path+self.botId)   
            self.env.networkEnv.updateByWaNum(self.botId)            
            self.sendLayer.db = self.profile.axolotl_manager  
            
        self._stack = stackBuilder\
            .pushDefaultLayers()\
            .push(self.sendLayer)\
            .build()
        self._stack.setProp("env",self.env)        
        self._stack.setProp("ID_TYPE",self.idType)

        self.bot_type = bot_type              
        self.callback = self.onCallback      
        self.inloop = False

        self.manualStop = False                

        self.cmdEventMap = {}
        
        if self.bot_type==YowBotType.TYPE_REG_COMPANION:                   
            identity = KeyHelper.generateIdentityKeyPair()
            self._stack.setProp("reg_info",{
                "keypair":WATools.generateKeyPair(),
                "regid": KeyHelper.generateRegistrationId(False),
                "identity": identity,            
                "signedprekey": KeyHelper.generateSignedPreKey(identity,0)
            })

        self.cmdList = {}
        if self.botId is not None:
            self._stack.setProfile(self.profile)                                  
            members = inspect.getmembers(YowBot, predicate = inspect.isfunction)
            for m in members:            
                if hasattr(m[1], "desc"):  
                    self.cmdList[m[1].cmd] = m[1]       

    def onCallback(self,event=None,message=None,cmdresult=None,logger=logger,caller=None):

        if cmdresult is not None:
            logger.info(cmdresult)

        if event is not None:   
            if event.HasField("contact_update"):
                logger.info("Contact %s notification:  %s : %s" %(event.contact_update.target,event.contact_update.key,event.contact_update.value))                     
            elif event.HasField("msg_log"):
                if event.msg_log.error_code:
                    logger.info("MsgLog %s-%s (ID=%s) from %s" % (wsend_pb2.MsgLogItem.Status.Name(event.msg_log.status),event.msg_log.error_code,event.msg_log.msg_id,event.bot_id))
                else:
                    logger.info("MsgLog %s(ID=%s) from %s" % (wsend_pb2.MsgLogItem.Status.Name(event.msg_log.status),event.msg_log.msg_id,event.msg_log.target))

            else:
                logger.info("Event %s from %s" % (wsend_pb2.BotEvent.Event.Name(event.event),event.bot_id))
            
        if message is not None:
            if message.HasField("participant"):
                src = "%s::%s" % (message.sender ,message.participant)
            else:
                src = message.sender
            dst = message.target                
            if message.HasField("text_message"):
                logger.info("Receive text message \"%s\" from %s to %s" % (message.text_message.text,src,dst))  
            else:
                logger.info("Receive %s message from %s to %s" % (wsend_pb2.Message.Type.Name(message.type),src,dst)) 


    def getCmdList(self):
        return self.cmdList

    def run(self):     
        
        if self.bot_type==YowBotType.TYPE_REG_COMPANION:
            logger.info("QRScan Registration Start")
        else:
            logger.info("Login start")           
            logger.info("AccountFile=%s" % self.profile)

        while True:                     
            try :                            
                self.inloop = True            
                self._stack.broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECT))                                         
                self._stack.loop()   

                if self.sendLayer.userQuit:
                    break

            except KeyboardInterrupt:      
                self.inloop = False
                self.disconnect()       
                break     
            except socks.SOCKS5Error:
                logger.info("PROXY ERROR, CHANGE IP AND RECONNECT")
                self.env.networkEnv.changeIP(self.bot_api.botId)     
            except OSError:
                self.inloop = False 
                self.disconnect()              
                break
    
            
    def waitLogin(self):
        return self.sendLayer.waitLogin()

    def printUsage():
        members = inspect.getmembers(YowBot, predicate = inspect.isfunction)
        print("[command]           |   [description]")
        print("-----------------------------------------------------------------------")
        for m in members:            
            if hasattr(m[1], "desc"):                
                fn = m[1]
                print("%s|\t%s" % (m[1].cmd.ljust(20,' '), m[1].desc.ljust(50,' ')))
        print("-----------------------------------------------------------------------")

    def disconnect(self):        
        self.sendLayer.userQuit = True        
        self.sendLayer.setProp("FORCEQUIT",1)                  
        if self.inloop:
            self._stack.broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT))
        else:
            self.sendLayer.onDisconnected(YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT))  

    def quit(self)  :               
        self.disconnect()

    def callDirect(self,name,params,options):
        cmdId = None
        fn = self.cmdList[name] if name in self.cmdList else None   
        if fn is not None:            
            try:
                cmdId = fn(self,params,options) 
                if cmdId not in self.cmdEventMap:
                    #非直返结果
                    self.cmdEventMap[cmdId] = {"event":threading.Event()}
            except ParamsNotEnoughException:
                return None,{"code":-1,"msg":"Params Not Enough"}
                        
            if cmdId is None:
                return None,{"code":-3,"msg":"No CmdId Return"}
            
            return cmdId,None
        else:
            logger.info("command %s not found" % name)
            return None,{"code":-2,"msg":"Command Not Found"}

    def checkCmdResult(self,cmdId):        
        if cmdId not in self.cmdEventMap:
            return False        
        obj =self.cmdEventMap[cmdId]                
        return  obj["event"].isSet() 
    
    def getCmdResultDirect(self,cmdId):                
        if cmdId in self.cmdEventMap:
            obj =self.cmdEventMap[cmdId]
            del self.cmdEventMap[cmdId]
            if "error" in obj :
                return None,obj["error"]        
            elif "result" in obj :
                return obj["result"],None
            else:
                return None,None
        else:
            return None,{"code":-4,"msg":"cmdId not found"}

    def getCmdResult(self,cmdId,waitTime):
        if cmdId in self.cmdEventMap:
            obj =self.cmdEventMap[cmdId]
            if obj["event"].wait(waitTime):
                del self.cmdEventMap[cmdId]
                if "error" not in obj :
                    return obj["result"],None
                else:
                    return None,obj["error"]        
            else:
                return None,{"code":-999,"msg":"timeout"}                
        else:
            return None,{"code":-4,"msg":"cmdId not found"}
        
    def setCmdError(self,cmdId,error):
        if cmdId in self.cmdEventMap: 
            obj = self.cmdEventMap[cmdId]
            obj["error"] = error         
            obj["event"].set()  

    def setCmdResult(self,cmdId,result):

        if cmdId in self.cmdEventMap:            
            obj = self.cmdEventMap[cmdId]
            obj["result"] = result
            if obj["event"]:
                if obj["event"]=="callback":
                    self.callback(cmdresult={
                        "botId": self.botId,
                        "cmdId":cmdId,
                        "result":result,
                        "timestamp":int(time.time())
                    })
                else:                                   
                    obj["event"].set()    
        else:
            e = threading.Event()
            e.set()            
            self.cmdEventMap[cmdId] = {"result":result,"event":e}          

    def callWaitResult(self,name,params,options,waitResultTime=20):

        cmdId,errMsg = self.callDirect(name,params,options)

        if cmdId is None:
            logger.info("Command %s error(execute stage），info=%s" % (name,errMsg))                  
            return None,errMsg
        
        result,errMsg = self.getCmdResult(cmdId,waitResultTime)
        
        if errMsg is not None:
            logger.info("Command %s error(result stage），info=%s" % (name,errMsg)) 
            return None,errMsg

        else:            
            logger.info("Command %s complete，result=%s" % (name,json.dumps(result)))
            return result,None

    '''
    =========================THE FOLLOWING is THE DEMO COMMANDS ==========================
    '''
    
    @BotCmd("send","send message to peer")
    def sendMsg(self,params,options):                 
        return self.sendLayer.sendMsg(params,options)     

    @BotCmd("sendmedia","send media message to  peer")
    def sendMediaMsg(self,params,options):                    
        return self.sendLayer.sendMediaMsg(params,options)  


    @BotCmd("sync", "sync contacts")
    def syncContacts(self,params,options):                
        return self.sendLayer.syncContacts(params,options)

    @BotCmd("init", "initialize (first login)")        
    def intialize(self,params,options):    
        time.sleep(5)  #wait 5 seconds
        self.sendLayer.getConfig(params,options)    
        time.sleep(2)                
        self.setSelfName(params,options)
        return "JUSTWAIT"     
    
    @BotCmd("getgroupinvite", "get the invite code of a group")
    def getgroupinvite(self,params,options):
        return self.sendLayer.getGroupInvite(params,options)    
        
    @BotCmd("joingroup", "join group with a invite code")        
    def joinGroupWithCode(self,params,options):   
        return self.sendLayer.joinGroupWithCode(params,options)

    @BotCmd("leavegroup", "leave group")        
    def leavegroup(self,params,options):   
        return self.sendLayer.leaveGroup(params,options)

    @BotCmd("setavatar", "set account avatar")
    def setAvatar(self,params,options):                
        return self.sendLayer.setAvatar(params,options)  


    @BotCmd("setselfname", "set account name")
    def setSelfName(self, params,options):            
        if len(params)==0:
            params=[names.get_full_name()]
        self.profile.config.pushname = params[0]
        self.profile.write_config(self.profile.config)                         
        if self.env.deviceEnv.getOSName() in ["SMBA","SMB iOS"]:
            #call the api if set a business name
            return self.sendLayer.setBusinessName(params,options)
        else:            
            id = str(uuid.uuid4())
            self.sendLayer.setCmdResult(id,{
                "status":"OK"
            })        
            return id
            
    @BotCmd("set2fa","set account 2fa")
    def set2FA(self,params,options):
        return self.sendLayer.set2FA(params,options)

    @BotCmd("makegroup","make group with members")
    def makeGroup(self,params,options):
        return self.sendLayer.makeGroup(params,options)
    
    @BotCmd("groupadd","add member to group")
    def groupAdd(self,params,options):
        return self.sendLayer.groupAdd(params,options)
    

    @BotCmd("grouppromote","promote group member (to admin)")
    def groupPromote(self,params,options):
        return self.sendLayer.groupPromote(params,options)

    @BotCmd("groupdemote","demote group member (from admin) ")
    def groupDemote(self,params,options):
        return self.sendLayer.groupDemote(params,options)

    @BotCmd("groupremove","remove member from group ")
    def groupRemove(self,params,options):
        return self.sendLayer.groupRemove(params,options)

    @BotCmd("groupinfo","show the group info")
    def groupInfo(self,params,options):
        return self.sendLayer.groupInfo(params,options)

    @BotCmd("groupapprove","approve participants to join the group")
    def groupApprove(self,params,options):
        self.sendLayer.groupApprove(params,options)

    @BotCmd("setgroupicon","set icon for group")
    def setGroupPicture(self,params,options):
        return self.sendLayer.setGroupIcon(params,options)


    @BotCmd("getavatar", "get account avatar")
    def getAvatar(self,params,options):
        return self.sendLayer.getAvatar(params,options)

                      
if __name__ == "__main__":    
    
    SysVar.loadConfig()  

    # default-env  android,direct
    env = BotEnv(
        deviceEnv = DeviceEnv("android",random=True), 
        networkEnv = NetworkEnv(NetworkEnv.TYPE_DIRECT)
    )

    bot = YowBot(botId="212719800440",env=env)

    bot.run()
    

    
        


                            

                            




