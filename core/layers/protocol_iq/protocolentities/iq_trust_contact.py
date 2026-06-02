from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .iq import IqProtocolEntity
class TrustContactIqProtocolEntity(IqProtocolEntity):
    
    def __init__(self, jids,timestamp,_id = None ) -> None:
        super().__init__("privacy" , _id = _id, _type = "set",to="s.whatsapp.net")     
        self.jids = jids 
        self.timestamp = timestamp  

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        tokens = ProtocolTreeNode("tokens",{})
        jidList = self.jids.split(",")

        for jid in jidList:
            token = ProtocolTreeNode("token",{"jid":jid,"type":"trusted_contact","t":str(self.timestamp)})
            tokens.addChild(token)        
                        
        node.addChild(tokens)      
        
        return node    
