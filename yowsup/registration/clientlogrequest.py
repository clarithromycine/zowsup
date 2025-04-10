from yowsup.common.http.warequest import WARequest
from yowsup.common.http.waresponseparser import JSONResponseParser


class WAClientLogRequest(WARequest):

    def __init__(self, config=None,log_obj={},env=None):
        """
        :param config:
        :type config: Config
        """
        super(WAClientLogRequest,self).__init__(config,env)
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

