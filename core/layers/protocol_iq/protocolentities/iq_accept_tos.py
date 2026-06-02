from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .iq import IqProtocolEntity
class AcceptTosIqProtocolEntity(IqProtocolEntity):

    def __init__(self, noticeId,_id = None) -> None:
        super().__init__("tos" , _id = _id, _type = "set",to="s.whatsapp.net")
        self.noticeId = noticeId        

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()        
        nodeNotice = ProtocolTreeNode("notice",{"id":self.noticeId,"stage":"5"})
        node.addChild(nodeNotice)   
        return node    
