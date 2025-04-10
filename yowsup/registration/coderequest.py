from yowsup.common.http.warequest import WARequest
from yowsup.common.http.waresponseparser import JSONResponseParser
from yowsup.common.tools import WATools
from yowsup.registration.existsrequest import WAExistsRequest
from yowsup.registration.clientlogrequest import WAClientLogRequest

import time
import random


class WACodeRequest(WARequest):
    def __init__(self, method, config,env=None):
        """
        :type method: str
        :param config:
        :type config: yowsup.config.v1.config.Config
        """
        super(WACodeRequest,self).__init__(config,env)

        if env.deviceEnv.getOSName() in ["iOS","SMB iOS"]:
            self.addParam("recovery_token_error","-25300")            
        
        if env.deviceEnv.getOSName() in ["Android","SMBA"]:                        
            self.addParam("sim_type", '1')
            self.addParam("sim_num", '0')
            self.addParam("recaptcha",'{"stage":"ABPROP_DISABLED"}')            
            self.addParam("network_radio_type","1")
            self.addParam("hasincr","1")
            self.addParam("clicked_education_link","false")
            self.addParam("call_log_permission","false")
            self.addParam("education_screen_displayed","false")
            self.addParam("prefer_sms_over_flash","false")
            self.addParam("device_ram","5.59")        
            self.addParam("manage_call_permission","false")
            self.addParam("client_metric",'{"attempts":1,"app_campaign_download_source":"google_play|unknown","was_activated_from_stub":false}')
            self.addParam("airplane_mode_type",'0')
            self.addParam("feo2_query_status",'error_security_exception')
            self.addParam("hasav",'2')
            self.addParam("mistyped",'6')
            self.addParam("roaming_type",'0')
            self.addParam("push_code","iLJ10zQsCT8%3D")       # need generate by GCM
            self.addParam("gpia","")            # need generate
            self.addParam("fid","")             # something new  (an uuid)
            self.addParam("backup_token","")    # 20 bytes
            
            self.addParam("recaptcha",'{"stage":"ABPROP_DISABLED"}')
            self.addParam("sim_type", '1')
            self.addParam("read_phone_permission_granted","0")
            self.addParam("pid","12246")
                    
        self.addParam("token", env.deviceEnv.getToken(self._p_in))
        self.addParam("mcc", "000")
        self.addParam("mnc", "000")
        self.addParam("sim_mcc", "000")
        self.addParam("sim_mnc", "000")
        self.addParam("method", method)           
        self.addParam("reason","")            
        self.addParam("cellular_strength",random.choice(["1","2","3","4","5"]))


        self.url = "v.whatsapp.net/v2/code"
                
        self.pvars = ["status","reason","length", "method", "retry_after", "code", "param"] +\
                    ["login", "type", "sms_wait", "voice_wait","audio_blob","image_blob"]
        self.setParser(JSONResponseParser())



    def send(self, parser = None, encrypt=True, preview=False):        
        
        ret,result = self.preStep(parser, encrypt, preview)
        if ret:          
            ret,result = self.rawSend(parser, encrypt, preview)            
            return result       
        else:
            return result
            
    def preStep(self, parser = None, encrypt=True, preview=False):

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

            request = WAExistsRequest(self._config,self.apnClient,self.env)
            result = request.send(encrypt=encrypt, preview=preview)               
            if result and result["status"] == "fail":
                if result["reason"] == "blocked" or result["reason"]=="format_wrong":
                    return False,result

            logReq = WAClientLogRequest(self._config,log_obj = {
                "current_screen":"verify_sms",
                "previous_screen":"enter_number",
                "action_taken":"continue"
            },env=self.env)                        
            result = logReq.send(preview=False)
            return True,result

    def rawSend(self, parser = None, encrypt=True, preview=False):
     
        result = super(WACodeRequest, self).send(parser, encrypt=encrypt, preview=preview)
        if result["status"]=="fail":                
            return False,result                
        return True,result        

