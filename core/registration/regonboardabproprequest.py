from ..common.http.warequest import WARequest
from typing import Optional, Any, Dict
from ..common.http.waresponseparser import JSONResponseParser


class WARegOnBoardAbPropRequest(WARequest):

    def __init__(self, cc: Optional[Any] = None, _in: Optional[Any] = None, ab_hash: Optional[Any] = None, config: Optional[Any] = None, env: Optional[Any] = None) -> None:

        super().__init__(config,env)

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

