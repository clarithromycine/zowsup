from .....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
class SetEmailIqProtocolEntity(IqProtocolEntity):

    def __init__(self, _id = None,email = "unknown4096@gmail.com") -> None:
        super().__init__("urn:xmpp:whatsapp:account" , _id = _id, _type = "set",to="s.whatsapp.net")
        self.email = email       
        
    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        nodeEmail = ProtocolTreeNode("email",{})
        nodeEmail.addChild(ProtocolTreeNode("email_address",{},None,self.email.encode("utf-8")))
        node.addChild(nodeEmail)      
        return node    
