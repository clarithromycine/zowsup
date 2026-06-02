from ..common.http.warequest import WARequest
from typing import Optional, Any, Dict
from ..common.http.waresponseparser import JSONResponseParser
from fcm_push_receiver.fcm_module import FcmModule
import base64
import binascii
from conf.constants import SysVar
import random


class WAExistsRequest(WARequest):


    def __init__(self, config: Optional[Any] = None, apnClient: Optional[Any] = None, fcmClient: Optional[Any] = None, env: Optional[Any] = None,  shareParamsDict: Optional[Any] = None) -> None:
        """
        :param config:
        :type config: yowsup.config.v1.config.Config
        """
        super().__init__(config,env)
        if config.id is None:
            raise ValueError("Config does not contain id")

        self.url = "v.whatsapp.net/v2/exist"

        self.pvars = ["status", "reason", "sms_length", "voice_length", "result","param", "login", "type",
                      "chat_dns_domain", "edge_routing_info"
                    ]

        self.setParser(JSONResponseParser())               
        self.addParam("token", self.env.deviceEnv.getToken(self._p_in))        

        if shareParamsDict:
            self.addAllParamsFromDict(shareParamsDict)

        if env.deviceEnv.getOSName()=="Android":
            self.addParam("mistyped",'6')

        if env.deviceEnv.getOSName()=="SMBA":
            self.addParam("mistyped",'7')            
            
        '''
        if self.env.deviceEnv.getOSName() in ["iOS","SMB iOS"]:
            self.addParam("offline_ab",'{"exposure":["hide_link_device_button_release_rollout_universe|hide_link_device_button_release_rollout_experiment|control","ios_confluence_tos_pp_link_update_universe|iphone_confluence_tos_pp_link_update_exp|test"],"metrics":{"expid_c":true,"fdid_c":true,"rc_c":true,"expid_md":1711209349,"expid_cd":1711209349}}')
            self.addParam("recovery_token_error","-25300")
        '''

        if self.env.deviceEnv.getOSName() in ["Android","SMBA"]:            
            self.addParam("offline_ab",'{"exposure":["android_offline_edge_to_edge_support_100_prod_universe|android_prod_100_offline_edge_to_edge_support_experiment|control","android_offline_dummy_aa_experiment_for_early_fetch|android_offline_dummy_aa_experiment_for_early_fetch_exp|test"],"exp_hash":["9682|android_offline_dummy_aa_experiment_for_early_fetch","376|android_offline_edge_to_edge_support_100_prod_universe"],"metrics":{}}')
            self.addParam("language_selector_clicked_count","0")
            self.addParam("language_selector_time_spent","0")                                                
            self.addParam("read_phone_permission_granted","0")     
            self.addParam("is_foa_fdid_app_installed","true")    
            self.addParam("backup_token_error","null_token")    
            self.addParam("network_operator_name","")
            self.addParam("sim_operator_name","")
            self.addParam("device_name","sagit") 
            self.addParam("sim_state",'1')
            self.addParam("client_metric",'{"attempts":1,"app_campaign_download_source":"google-play|unknown","was_activated_from_stub":false}')     
                                        
        


        if fcmClient is not None:
            push_token = fcmClient.getFcmToken()                 
            self.addParam("push_token",push_token)
            

        
        
        



   
