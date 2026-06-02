import sys,os
sys.path.append(os.getcwd())

import logging
from core.registration import LogoutFetchRequest
from core.config.manager import ConfigManager
from conf.constants import SysVar
from core.profile.profile import YowProfile
from common.utils import Utils
from common.consolemain import ConsoleMain
import traceback,base64
from core.config.v1.serialize import ConfigSerialize
from core.config.transforms.dict_json import DictJsonTransform
from core.axolotl.factory import AxolotlManagerFactory
from proto import zowsup_pb2 
import json
import uuid


logger = logging.getLogger(__name__)
class LogoutFetch(ConsoleMain):

    def run(self,params,options):
        number = params[0]       

        self.commonOptionsProcess(options)   

        if "output" not in options:
            options["output"] = "db"               


        if "env" not in options:
            options["env"] = SysVar.DEFAULT_ENV
            logger.info("set default env to %s" % options["env"])
            
        regType,osType = Utils.getTypesByEnvName(options["env"])
                              
        config_manager = ConfigManager()
        config = config_manager.load(SysVar.ACCOUNT_PATH+number)
        profile = YowProfile(number, config)

        try:
            req = LogoutFetchRequest(config, self.env)            
            result = req.send(preview=False)     
            profile.write_config(config)    

            if result["status"]=="ok" or (result["status"]=="fail" and result["reason"]=="not_allowed"):        #not_allowed是个奇怪的状态，有时候会这样
                
                jsonstr = DictJsonTransform().transform(ConfigSerialize(config.__class__).serialize(config))
                db = AxolotlManagerFactory().get_manager(SysVar.ACCOUNT_PATH+number,number)
                signedprekey = db.load_latest_signed_prekey(generate=True)

                publicKey = str(base64.b64encode(db.identity.publicKey.serialize()),'UTF-8')
                privateKey = str(base64.b64encode(db.identity.privateKey.serialize()),'UTF-8') 

                kp = config.client_static_keypair

                lg,lc = Utils.getLGLC(config.cc)

                fullData = {
                    "jid":config.phone,
                    "registrationID":db.registration_id,
                    "identityPublicKey":str(base64.b64encode(db.identity.publicKey.serialize()[1:]),'UTF-8'),
                    "identityPrivateKey":str(base64.b64encode(db.identity.privateKey.serialize()),'UTF-8') ,
                    "phoneUUID":config.fdid,
                    "deviceUUID":str(uuid.UUID(int=int.from_bytes(config.expid, 'little'))),
                    "osVersion":self.env.deviceEnv.getOSVersion(),
                    "manufacturer":self.env.deviceEnv.getManufacturer(),
                    "device":self.env.deviceEnv.getDeviceName2(),
                    "osBuildNumber":self.env.deviceEnv.getDeviceModelType(),
                    "mcc":"000",
                    "mnc":"000",
                    "language": lg,
                    "country": lc,
                    "cc":config.cc,
                    "in":config.phone[len(config.cc):],
                    "clientStaticPrivateKey":str(base64.b64encode(kp.private.data),"UTF-8"),
                    "clientStaticPublicKey":str(base64.b64encode(kp.public.data),"UTF-8"),
                    "signPreKeyID":signedprekey.getId(),
                    "signPreKeyPublicKey":str(base64.b64encode(signedprekey.getKeyPair().publicKey.serialize()[1:]),"UTF-8"),
                    "signPreKeyPrivateKey":str(base64.b64encode(signedprekey.getKeyPair().privateKey.serialize()),"UTF-8"),
                    "signPreKeySignature":str(base64.b64encode(signedprekey.getSignature()),"UTF-8"),
                    "whatsappVersion":self.env.deviceEnv.getVersion()
                }





                channel = Utils.profile2Channel(config,db)

                Utils.outputResult({
                    "retcode":0,            
                    "msg":"success",                    
                    "channel": channel,
                    "details":result,                              
                })    

                return {
                    "retcode":0,
                    "data":channel,
                    "fullData":json.dumps(fullData)
                }   
                                                   
            else:
                Utils.outputResult({
                    "retcode":-1,
                    "msg":"fail in register command, check the number status",
                    "details": result,                    
                })

                return {
                    "retcode":-1,
                    "result":result
                }
        except:
            logger.error(traceback.format_exc())
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
    LogoutFetch().run(params,options)