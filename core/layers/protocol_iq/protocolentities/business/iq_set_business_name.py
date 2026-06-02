from .....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
from common.utils import Utils
from .....common import YowConstants
from proto import e2e_pb2
import random

class SetBusinessNameIqProtocolEntity(IqProtocolEntity):

    def __init__(self, _id = None,profile=None,name = "default.chinago") -> None:
        super().__init__("w:biz" , _id = _id, _type = "set",to="s.whatsapp.net")
        self.name = name
        self.profile = profile          #传profile 主要是要拿私钥

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()     
        payload = Utils.vnamePayload(self.name,self.profile.axolotl_manager.identity.privateKey)
        cert = ProtocolTreeNode("verified_name",{"v":"2"},None,payload.SerializeToString())        
        node.addChild(cert)  
               
        return node


class SetBusinessNameResultIqProtocolEntity(IqProtocolEntity):

    def __init__(self,_id=None) -> None:
        super().__init__(_id = _id, _type = "result",to=YowConstants.DOMAIN)
        self.nameId = None
        
    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)        
        entity.__class__ = SetBusinessNameResultIqProtocolEntity
        resultNode = node.getChild("verified_name")  
        if resultNode is not None:
            entity.nameId = resultNode.getAttributeValue("id")                
            return entity
        else:
            return None