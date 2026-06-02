from ....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .iq import IqProtocolEntity

class AppSyncResetIqProtocolEntity(IqProtocolEntity):

    def __init__(self, _id = None) -> None:
        super().__init__("w:sync:app:state" , _id = _id, _type = "set",to="s.whatsapp.net")
        self.type = type

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        x = ProtocolTreeNode("delete_all_data",{})
        node.addChild(x)      
        return node    
