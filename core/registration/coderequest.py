from ..common.http.warequest import WARequest
from typing import Optional, Any, Dict
from ..common.http.waresponseparser import JSONResponseParser
from ..common.tools import WATools
from ..registration.existsrequest import WAExistsRequest
from ..registration.clientlogrequest import WAClientLogRequest

from conf.constants import SysVar
import time,os,logging,uuid
import random,threading
from fcm_push_receiver.fcm_module import FcmModule
from ..layers.protocol_iq.protocolentities  import *


logger = logging.getLogger(__name__)
class WACodeRequest(WARequest):

    def __init__(self, method: Optional[Any] = None, config: Optional[Any] = None, env: Optional[Any] = None) -> None:
        """
        :type method: str
        :param config:
        :type config: yowsup.config.v1.config.Config        
        """        
        super().__init__(config,env)
        
        self.shareParamsDict = {                        
            "access_session_id":self.b64encode(os.urandom(16),padding=False),                      
            "advertising_id": "a1c2815d-6304-4cb5-a379-fac4621642d7",               
            "backup_token": os.urandom(20),                        
            "sim_type": "0",
            "network_radio_type":"1",
            "pid":str(random.randint(10000,50000)),
            "device_ram":"3.75",
            "airplane_mode_type":"0",
            "cellular_strength":"5",
            "hasinrc":"1",
            "db":"1",
            "roaming_type":"0",            
            "feo2_query_status":"error_security_exception",
            "recaptcha":'{"stage":"ABPROP_DISABLED"}',
            "simnum":"0"
        }

        config.aid = self.b64encode(os.urandom(32),padding=True).decode()
        self.shareParamsDict["aid"] = config.aid

        if env.deviceEnv.getOSName() in ["iOS","SMB iOS"]:
            self.addParam("recovery_token_error","-25300")            
            self.addParam("method", method)    
            self.addParam("mcc", "000")
            self.addParam("mnc", "000")
            self.addParam("sim_mcc", "000")
            self.addParam("sim_mnc", "000")              
            self.addParam("reason","")  
            self.addParam("hasav",'2')
            self.addParam("prefer_sms_over_flash","false")
            self.addParam("education_screen_displayed","false")       
            self.addParam("mistyped",'6')     


        self.addAllParamsFromDict(self.shareParamsDict)

        
        if env.deviceEnv.getOSName()=="Android":
            self.addParam("mistyped",'6')

        if env.deviceEnv.getOSName()=="SMBA":
            self.addParam("mistyped",'7')  
                
        if env.deviceEnv.getOSName() in ["Android","SMBA"]:                                                               
            self.addParam("method", method)    
            self.addParam("client_metric",'{"attempts":1,"app_campaign_download_source":"google_play|unknown"}')                        
            self.addParam("reason","")  
            self.addParam("hasav",'2')
            self.addParam("prefer_sms_over_flash","false")
            self.addParam("education_screen_displayed","false")
            self.addParam("mcc", "000")
            self.addParam("mnc", "000")
            self.addParam("sim_mcc", "000")
            self.addParam("sim_mnc", "000")                   
                                        
        self.addParam("token", env.deviceEnv.getToken(self._p_in))
        


        self.url = "v.whatsapp.net/v2/code"
                
        self.pvars = ["status","reason","length", "method", "retry_after", "code", "param"] +\
                    ["login", "type", "sms_wait", "voice_wait","audio_blob","image_blob"]
        self.setParser(JSONResponseParser())
    
        self.apnClient = None
        if env.deviceEnv.getOSName() in ["iOS","SMB iOS"] and method in ["sms","voice","flash"]:   
            self.apnClient = ApnClient(self.getParam("fdid"),env.networkEnv)

        self.fcmClient = None
        if env.deviceEnv.getOSName() in ["Android","SMBA"] and method in ["sms","voice","flash"]:      
            fcmConfig = FcmModule.ANDROID_DEFAULT if env.deviceEnv.getOSName() == "Android" else FcmModule.SMB_ANDROID_DEFAULT
            self.fcmClient = FcmModule(fcmConfig,False,None)        
            self.fcmClient.startMessageListener(self.fcmMsgCallback)   
        self.push_code = None 

        self.fcmCodeEvent = threading.Event()        
        
    async def fcmMsgCallback(self,obj,data,p):
        if data["id"]=="RegistrationVerification":                        
            logger.info("push_code received")
            self.push_code = data["registration_code"]  
            self.fcmCodeEvent.set()   

        if data["id"]=="ban_appeals":
            logger.info("device may be banned !!!!!!,please change the fcm token")
               
    def send(self, parser = None, encrypt=True, preview=False) -> Any:        
        
        ret,result = self.preStep(parser = None, encrypt=True, preview=False)
        if ret:                        
            ret,result = self.rawSend(parser = None, encrypt=True, preview=False)            
            return result       
        else:
            return result

    def preStep(self, parser = None, encrypt=True, preview=False) -> Any:

        if self._config.id is not None:
            request = WAExistsRequest(self._config,self.apnClient,self.env)            
            result = request.send(encrypt=encrypt, preview=preview)                        
            if result:                
                if result["status"] == "ok":
                    return True,result
                elif result["status"] == "fail" and "reason" in result and (result["reason"] == "blocked" or result["reason"] == "temporarily_unavailable"): 
                    return False,result
                            
            return True,result
        else:    
            self._config.id = WATools.generateIdentity()
            self.addParam("id", self._config.id)            
                       
            request = WAExistsRequest(self._config,self.apnClient,self.fcmClient,self.env,shareParamsDict = self.shareParamsDict)
            result = request.send(encrypt=encrypt, preview=preview)                        
            if result and result["status"] == "fail":
                if result["reason"] == "blocked" or result["reason"]=="format_wrong":
                    return False,result
                                            
            return True,result


    def rawSend(self, parser = None, encrypt=True, preview=False) -> Any:

        #self.fcmClient = None

        if self.apnClient is not None:
            push_code = self.apnClient.getPushCode()

            if push_code is not None:
                self.addParam("push_code",push_code)           
                res = super().send(parser, encrypt=encrypt, preview=preview)
            else:
                #res = 
                # super(WACodeRequest, self).send(parser, encrypt=encrypt, preview=preview,cert = self.apnClient.getDeviceCert())
                return False,{"status":"fail","reason":"push_code"}
        elif self.fcmClient is not None:            
            self.fcmCodeEvent.wait(30)                        
            if self.push_code is not None:
                self.addParam("push_code",self.push_code)            
                result = super().send(parser, encrypt=encrypt, preview=preview)
            else:
                return False,{"status":"fail","reason":"push_code"}
        else:            
            result = super().send(parser, encrypt=encrypt, preview=preview)
            if result["status"]=="fail":                
                return False,result                
        return True,result        

