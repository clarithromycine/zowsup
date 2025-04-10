from yowsup.common.http.warequest import WARequest

class WAReset2FARequest(WARequest):

    def __init__(self, config=None,wipe_token=None,env=None):

        super(WAReset2FARequest,self).__init__(config,env)
        if config.id is None:
            raise ValueError("Config does not contain id")

        self.url = "v.whatsapp.net/v2/security"
