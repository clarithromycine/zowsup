from ..common.http.warequest import WARequest
from typing import Optional, Any, Dict


class LogoutFetchRequest(WARequest):

    def __init__(self, config: Optional[Any] = None, env: Optional[Any] = None) -> None:

        super().__init__(config,env)
        if config.id is None:
            raise ValueError("Config does not contain id")
        
        if env.deviceEnv.getOSName() in ["Android","SMBA"]:                                    
            self.addParam("sim_num", '0')        
            self.addParam("network_radio_type","1") 
            self.addParam("hasincr","1")                                                            
            self.addParam("client_metric",'{"attempts":64}')                        
            self.addParam("mistyped",'6')           
            self.addParam("backup_token","")                    
            self.addParam("pid","12246")
                    
        self.addParam("token", env.deviceEnv.getToken(self._p_in)) 
        self.addParam("mcc", "000")      
        self.addParam("mnc", "000")      
        self.addParam("sim_mcc", "000")  
        self.addParam("sim_mnc", "000")        
        self.addParam("reason","")                       

        self.url = "v.whatsapp.net/v2/device_logout_fetch"
