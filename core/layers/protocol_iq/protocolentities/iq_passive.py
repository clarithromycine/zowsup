from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .iq import IqProtocolEntity
class PassiveIqProtocolEntity(IqProtocolEntity):
    
    def __init__(self, _id = None) -> None:
        super().__init__("passive" , _id = _id, _type = "set",to="s.whatsapp.net")        

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        clean = ProtocolTreeNode("active",{})
        node.addChild(clean)      
        return node    
