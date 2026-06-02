from ..iq import IqProtocolEntity
from typing import Optional, Any, List, Dict, Union
from .....structs import ProtocolTreeNode
from .....common import YowConstants

import base64
class PushGetCatIqProtocolEntity(IqProtocolEntity):
    def __init__(self,token) -> None:
        super().__init__("urn:xmpp:whatsapp:push", _type="get",to="s.whatsapp.net")
        self.token = token

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()        
        node.addChild(ProtocolTreeNode("pn",data=self.token.encode()))        
        return node
    
        
class PushGetCatResultIqProtocolEntity(IqProtocolEntity):


    def __init__(self,_id=None) -> None:
        super().__init__(_id = _id, _type = "result",to=YowConstants.DOMAIN)
        self.catData = None        

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = PushGetCatResultIqProtocolEntity

        catNode = node.getChild("cat")         #以出现这个字段为正确返回
        if catNode is not None:      
            entity.catData = catNode.getData()            
            return entity
        else:
            return None