from yowsup.common.http.warequest import WARequest
from yowsup.common.http.waresponseparser import JSONResponseParser
import random

class WAExistsRequest(WARequest):


    def __init__(self, config,env=None):
        """
        :param config:
        :type config: yowsup.config.v1.config.Config
        """
        super(WAExistsRequest,self).__init__(config,env)
        if config.id is None:
            raise ValueError("Config does not contain id")

        self.url = "v.whatsapp.net/v2/exist"

        self.pvars = ["status", "reason", "sms_length", 
                      "voice_length", "result","param", "login", "type",
                      "chat_dns_domain", "edge_routing_info"
                    ]

        self.setParser(JSONResponseParser())
               
        self.addParam("token", self.env.deviceEnv.getToken(self._p_in))
        
    
        if self.env.deviceEnv.getOSName() in ["iOS","SMB iOS"]:
            self.addParam("offline_ab",'{"exposure":["hide_link_device_button_release_rollout_universe|hide_link_device_button_release_rollout_experiment|control","ios_confluence_tos_pp_link_update_universe|iphone_confluence_tos_pp_link_update_exp|test"],"metrics":{"expid_c":true,"fdid_c":true,"rc_c":true,"expid_md":1711209349,"expid_cd":1711209349}}')
            self.addParam("recovery_token_error","-25300")

        if self.env.deviceEnv.getOSName() in ["Android","SMBA"]:
            self.addParam("gpia","")            # need generate
            self.addParam("read_phone_permission_granted","0")
            self.addParam("offline_ab",'{"exposure":["android_confluence_tos_pp_link_update_universe|android_confluence_tos_pp_link_update_exp|control"],"metrics":{}')
            self.addParam("device_ram","5.59")
            self.addParam("fid","")             # something new  (an uuid)
            self.addParam("language_selector_clicked_count","0")
            self.addParam("language_selector_time_spent","0")
            self.addParam("backup_token","")    # 20 bytes
            self.addParam("roaming_type",'0')
            self.addParam("mistyped",'7')
            self.addParam("feo2_query_status",'error_security_exception')
            self.addParam("sim_num", '0')
            self.addParam("sim_state",'5')
            self.addParam("airplane_mode_type",'0')
            self.addParam("client_metric",'{"attempts":28,"app_campaign_download_source":"google-play|unknown","was_activated_from_stub":false}')
            self.addParam("push_token","")       # need generate by GCM
            self.addParam("device_name","sagit")    
            self.addParam("hasincr","1")
            self.addParam("backup_token_error","null_token")
            self.addParam("network_radio_type","1")
            self.addParam("network_operator_name","SMART")
            self.addParam("cellular_strength",random.choice(["1","2","3","4","5"]))
            self.addParam("sim_operator_name","China Mobile")
            self.addParam("pid","12246")



