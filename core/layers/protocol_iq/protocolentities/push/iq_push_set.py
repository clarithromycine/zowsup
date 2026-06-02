from ..iq import IqProtocolEntity
from typing import Optional, Any, List, Dict, Union
from .....structs import ProtocolTreeNode

import base64
class PushSetIqProtocolEntity(IqProtocolEntity):

    '''
    <iq to='s.whatsapp.net' xmlns='urn:xmpp:whatsapp:push' type='set' id='01'>
        <config id='f2bWNmU-TGeCFJ4FuXiMnx:APA91bGr_vhFmmTWAHnAMRvW4b_lIIdd1PzWjuqehsVOzzf7tw2rMcFkxXqaN3jnV6y_3MeZ1ST6fw1ZzT8yg48CJWecbm-9j6jPJ9ytMivPITyutV3FDX0' 
            pkey='TzrmlIudBJ3zvLuZgV83krgYjbAk-ddWF4Vr7HTcXkw' num_acc='1' platform='gcm' voip_payload_type='2'/>
    </iq>
    '''
    def __init__(self,id,pkey=None,numAcc=1,platform="gcm",voipPayloadType=2) -> None:        
        super().__init__("urn:xmpp:whatsapp:push", _type="set",to="s.whatsapp.net")
        self.id = id
        self.pkey = pkey
        self.numAcc = numAcc
        self.platform = platform
        self.voipPayloadType = voipPayloadType

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()        

        config = {"id":self.id,
                  "platform":self.platform,
                  "num_acc":str(self.numAcc),
                  "voip_payload_type":str(self.voipPayloadType)
        }

        if self.pkey is not None:
            config["pkey"]=self.pkey

        node.addChild(ProtocolTreeNode("config",config))
        return node
    
