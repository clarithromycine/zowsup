from ..common.http.warequest import WARequest
from typing import Optional, Any, Dict

class WAReset2FARequest(WARequest):

    def __init__(self, config: Optional[Any] = None, wipe_token: Optional[Any] = None, env: Optional[Any] = None) -> None:

        super().__init__(config,env)
        if config.id is None:
            raise ValueError("Config does not contain id")
        
        self.addParam("reset","wipe")
        self.addParam("wipe_token",wipe_token)

        self.url = "v.whatsapp.net/v2/security"
