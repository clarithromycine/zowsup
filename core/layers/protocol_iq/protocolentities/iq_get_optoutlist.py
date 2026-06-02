from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .iq import IqProtocolEntity
class GetOptoutlistIqProtocolEntity(IqProtocolEntity):

    def __init__(self, _id = None) -> None:
        super().__init__("optoutlist" , _id = _id, _type = "get",to="s.whatsapp.net")
                
    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        return node    
