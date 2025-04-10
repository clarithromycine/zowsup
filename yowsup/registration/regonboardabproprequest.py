

from yowsup.common.http.warequest import WARequest
from yowsup.common.http.waresponseparser import JSONResponseParser


class WARegOnBoardAbPropRequest(WARequest):

    def __init__(self,cc=None,_in=None,ab_hash=None,env=None):

        super(WARegOnBoardAbPropRequest,self).__init__(None,env)

        if cc is None:
            cc = "1"
            _in = "2155550000"

        self.addParam("cc", cc)
        self.addParam("rc","0")
        self.addParam("in",_in)

        if ab_hash is not None:
            self.addParam("ab_hash",ab_hash)
                
        self.pvars = ["status", "ab_hash"]        
        self.setParser(JSONResponseParser())
        
        self.url = "v.whatsapp.net/v2/reg_onboard_abprop"

        self.env = env

        