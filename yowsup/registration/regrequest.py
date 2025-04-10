
from yowsup.common.http.warequest import WARequest
from yowsup.common.http.waresponseparser import JSONResponseParser
import base64

from axolotl.ecc.curve import Curve
from yowsup.axolotl.factory import AxolotlManagerFactory

from proto import e2e_pb2
import random
from yowsup.registration.clientlogrequest import WAClientLogRequest

class WARegRequest(WARequest):

    def __init__(self, config, code,env=None):
        """
        :param config:
        :type config: yowsup.config.vx.config.Config
        :param code:
        :type code: str
        """
        super(WARegRequest,self).__init__(config,env)

        if config.id is None:
            raise ValueError("config.id is not set.")

        self.addParam("code", code)

        if env.deviceEnv.getOSName()=="SMB iOS": 
            logReq = WAClientLogRequest(self._config,log_obj = {
                    "event_name":"smb_client_onboarding_journey",
                    "is_logged_in_on_consumer_app":"0",
                    "sequence_number":"14",
                    "app_install_source":"unknown|unknown",
                    "smb_onboarding_step":"20",
                    "has_consumer_app":"1"

                },env=self.env)                            
            logReq.send(preview=False)
                
        if env.deviceEnv.getOSName() in ["SMBA","SMB iOS"]:
            payload = e2e_pb2.VerifiedNameCertificate()            
            details = e2e_pb2.VerifiedNameCertificate.Details()
            details.serial = random.randint(1,1000000000000000)                   
            details.issuer = "smb:wa"        
            details.verifiedName = config.pushname  
            payload.details.MergeFrom(details)                            
            db = AxolotlManagerFactory().get_manager(config.phone,config.phone)                            
            payload.signature = Curve.calculateSignature(db.identity.privateKey,payload.details.SerializeToString())
            self.addParam("vname",str(base64.urlsafe_b64encode(payload.SerializeToString()),"utf-8"))

        self.addParam("entered",1)
        self.addParam("network_operator_name","SMART")
        self.addParam("sim_operator_name","SMART 5G")

        self.url = "v.whatsapp.net/v2/register"

        self.pvars = ["status", "login", "autoconf_type", "security_code_set","type", "edge_routing_info", "chat_dns_domain"
                      ,"retry_after","reason"]

        self.setParser(JSONResponseParser())
