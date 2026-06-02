from ..common.http.warequest import WARequest
from typing import Optional, Any, Dict
from ..common.http.waresponseparser import JSONResponseParser
import base64

from axolotl.ecc.curve import Curve
from ..axolotl.factory import AxolotlManagerFactory

from proto import e2e_pb2
import random
from ..registration.clientlogrequest import WAClientLogRequest
from common.utils import Utils

class WARegRequest(WARequest):

    def __init__(self, config: Optional[Any] = None, code: Optional[Any] = None, env: Optional[Any] = None) -> None:
        """
        :param config:
        :type config: yowsup.config.vx.config.Config
        :param code:
        :type code: str
        """
        super().__init__(config,env)

        if config.id is None:
            raise ValueError("config.id is not set.")

        self.addParam("code", code)

        if env.deviceEnv.getOSName()=="SMB iOS": 
            logReq = WAClientLogRequest(self._config,log_obj = {
                    "event_name":"smb_client_onboarding_journey",
                    "is_logged_in_on_consumer_app":"1",
                    "sequence_number":"14",
                    "app_install_source":"unknown|unknown",
                    "smb_onboarding_step":"20",
                    "has_consumer_app":"1"

                },env=self.env)                            
            logReq.send(preview=False)
                
        if env.deviceEnv.getOSName() in ["SMBA","SMB iOS"]:
            payload = Utils.vnamePayload(config.pushname,AxolotlManagerFactory().get_manager(config.phone,config.phone).identity.privateKey)
            self.addParam("vname",str(base64.urlsafe_b64encode(payload.SerializeToString()),"utf-8"))

        self.addParam("entered",1)
        self.addParam("network_operator_name","SMART")
        self.addParam("sim_operator_name","SMART 5G")

        self.url = "v.whatsapp.net/v2/register"

        self.pvars = ["status", "login", "autoconf_type", "security_code_set","type", "edge_routing_info", "chat_dns_domain"
                      ,"retry_after","reason"]

        self.setParser(JSONResponseParser())
