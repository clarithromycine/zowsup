from ..common.http.warequest import WARequest
from typing import Optional, Any, Dict

import random

class LogoutSendRequest(WARequest):

    def __init__(self, config: Optional[Any] = None, env: Optional[Any] = None) -> None:

        super().__init__(config,env)
        if config.id is None:
            raise ValueError("Config does not contain id")


        if env.deviceEnv.getOSName() in ["Android","SMBA"]:                        
            self.addParam("sim_type", '1')
            self.addParam("sim_num", '0')       
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
            self.addParam("backup_token","")    # 20 bytes

            self.addParam("sim_type", '1')
            self.addParam("read_phone_permission_granted","0")
            self.addParam("pid","12246")
                    
        self.addParam("token", env.deviceEnv.getToken(self._p_in))
        self.addParam("mcc", "000")
        self.addParam("mnc", "000")
        self.addParam("sim_mcc", "000")
        self.addParam("sim_mnc", "000")        
        self.addParam("reason","")            
        self.addParam("cellular_strength",random.choice(["1","2","3","4","5"]))

        self.url = "v.whatsapp.net/v2/device_logout_send"