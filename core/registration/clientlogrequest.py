from ..common.http.warequest import WARequest
from typing import Optional, Any, Dict
from ..common.http.waresponseparser import JSONResponseParser


class WAClientLogRequest(WARequest):

    def __init__(self, config: Optional[Any] = None, log_obj: Optional[Any] = {}, env: Optional[Any] = None) -> None:
        """
        :param config:
        :type config: Config
        """
        super().__init__(config,env)
        if config.id is None:
            raise ValueError("Config does not contain id")
        
        for key,val in log_obj.items():
            self.addParam(key,val)

        self.url = "v.whatsapp.net/v2/client_log"

        self.pvars = ["status", "login"]
        self.setParser(JSONResponseParser())

        if env is not None:
            self.addParam("token", env.deviceEnv.getToken(self._p_in))
        else:
            raise Exception("MUST SPECIFY A ENV")
        #self.addParam("funnel_id",uuid.uuid4()) #自动生成一个,不知道有什么用

