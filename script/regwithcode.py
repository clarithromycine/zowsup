import sys,os
sys.path.append(os.getcwd())
from common.consolemain import ConsoleMain
import logging
from core.profile.profile import YowProfile
from core.registration import *
from core.config.manager import ConfigManager
from conf.constants import SysVar
from core.axolotl.factory import AxolotlManagerFactory
from common.utils import Utils
import traceback
import json,base64,uuid
from core.config.v1.serialize import ConfigSerialize
from core.config.transforms.dict_json import DictJsonTransform
from proto import zowsup_pb2

logger = logging.getLogger(__name__)

class RegWithCode(ConsoleMain):
    
    def run(self,params,options):
                 
        number = params[0]
        code   = params[1]

        if "env" not in options:
            options["env"] = SysVar.DEFAULT_ENV
            logger.info("set default env to %s" % options["env"])
            
        self.commonOptionsProcess(options)       

                            

        if "output" not in options :
            options["output"] = "db"

           
        config_manager = ConfigManager()
        config = config_manager.load(SysVar.ACCOUNT_PATH+number)

        profile = YowProfile(number, config)

        self.env.networkEnv.updateProxyByWaNum(number)

        env = self.env.deviceEnv    

        regType,osType = Utils.getTypesByEnvName(options["env"])
        
     

        try:
            req = WARegRequest(config, code,self.env)            
            result = req.send(preview=False)            
            profile.write_config(config)

            if result["status"]=="fail" and result["reason"] == "consent" and result["pending"] == "dob":
                consentReq = WADobConsentRequest(config,self.env)
                result = consentReq.send(preview=False)   

            if result["status"]=="fail" and result["reason"] == "security_code" :
                if result["wipe_wait"] == 0:
                    reset2fareq = WAReset2FARequest(config,result["wipe_token"],self.env)            
                    result = reset2fareq.send(preview=False)         
                else:
                    result["context"] = Utils.profile2Context(SysVar.ACCOUNT_PATH+number,number)                    

            if result["status"]=="ok":        

                db = AxolotlManagerFactory().get_manager(SysVar.ACCOUNT_PATH+number,number)
                signedprekey = db.load_latest_signed_prekey(generate=True)
                kp = config.client_static_keypair
                lg,lc = Utils.getLGLC(config.cc)

                publicKey = str(base64.b64encode(db.identity.publicKey.serialize()),'UTF-8')
                privateKey = str(base64.b64encode(db.identity.privateKey.serialize()),'UTF-8')               
                jsonstr = DictJsonTransform().transform(ConfigSerialize(config.__class__).serialize(config))  

                fullData = {
                    "jid":config.phone,
                    "registrationID":db.registration_id,
                    "identityPublicKey":str(base64.b64encode(db.identity.publicKey.serialize()[1:]),'UTF-8').replace("/","\\/"),
                    "identityPrivateKey":str(base64.b64encode(db.identity.privateKey.serialize()),'UTF-8').replace("/","\\/"),
                    "phoneUUID":config.fdid,
                    "deviceUUID":str(uuid.UUID(int=int.from_bytes(config.expid, 'little'))),
                    "osVersion":self.env.deviceEnv.getOSVersion(),
                    "manufacturer":self.env.deviceEnv.getManufacturer(),
                    "device":self.env.deviceEnv.getDeviceName2(),
                    "osBuildNumber":self.env.deviceEnv.getDeviceModelType(),
                    "roProductBoard":self.env.deviceEnv.getDeviceName2(),
                    "roProductDevice":self.env.deviceEnv.getDeviceName2(),
                    "mcc":"000",
                    "mnc":"000",
                    "language": lg,
                    "country":lc,
                    "cc":config.cc,
                    "in":config.phone[len(config.cc):],
                    "clientStaticPrivateKey":str(base64.b64encode(kp.private.data),"UTF-8").replace("/","\\/"),
                    "clientStaticPublicKey":str(base64.b64encode(kp.public.data),"UTF-8").replace("/","\\/"),
                    "signPreKeyID":signedprekey.getId(),
                    "signPreKeyPublicKey":str(base64.b64encode(signedprekey.getKeyPair().publicKey.serialize()[1:]),"UTF-8").replace("/","\\/"),
                    "signPreKeyPrivateKey":str(base64.b64encode(signedprekey.getKeyPair().privateKey.serialize()),"UTF-8").replace("/","\\/"),
                    "signPreKeySignature":str(base64.b64encode(signedprekey.getSignature()),"UTF-8").replace("/","\\/"),
                    "whatsappVersion":self.env.deviceEnv.getVersion()
                }

                                
                req = WAClientLogRequest(config,env=self.env)
                req.send(preview=False)               
                Utils.outputResult({
                    "retcode":0,
                    "msg":"ok",
                    "data":Utils.profile2Channel(config,db),
                    "fullData":json.dumps(fullData)
                })   

                return {
                    "retcode":0,
                    "data":Utils.profile2Channel(config,db),
                    "fullData":json.dumps(fullData)
                }                   
                            
            else:
                Utils.outputResult({
                    "retcode":-1,
                    "msg":"fail",
                    "details":result,
                })   

                if result["reason"] == "device_confirm_or_second_code":
                    #这个错误需要后续处理，把当前的上下文记录下来一起上报
                    result["context"] = Utils.profile2Context(SysVar.ACCOUNT_PATH+number,number)                

                return {
                    "retcode":-1,
                    "result":result
                }                    

        except:
            Utils.outputResult({
                "retcode":-1,            
                "msg":"exception",
                "details":traceback.format_exc()
            })    
            sys.exit(1)   
                          
if __name__ == "__main__":

    SysVar.loadConfig()
    Utils.init_log(logging.INFO) 

    args = sys.argv      
    params,options = Utils.cmdLineParser(sys.argv)    
    RegWithCode().run(params,options)