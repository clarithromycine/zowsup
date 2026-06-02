from .....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
class VerifyEmailIqProtocolEntity(IqProtocolEntity):

    def __init__(self, _id = None) -> None:
        super().__init__("urn:xmpp:whatsapp:account" , _id = _id, _type = "set",to="s.whatsapp.net")

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        nodeEmail = ProtocolTreeNode("verify_email",{})
           
        nodeLg =  ProtocolTreeNode("lg",{},None,b"en")
        nodeEmail.addChild(nodeLg)
        nodeLg =  ProtocolTreeNode("lc",{},None,b"US")
        nodeEmail.addChild(nodeLg)
        node.addChild(nodeEmail)   
        return node    


class VerifyEmailResultIqProtocolEntity(IqProtocolEntity):

    def __init__(self,_id=None,waitTime=None,codeMatch=False) -> None:
        super().__init__(_id = _id, _type = "result",to=YowConstants.DOMAIN)
        self.waitTime = waitTime 
        self.codeMatch = codeMatch       

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = VerifyEmailResultIqProtocolEntity
        resultNode = node.getChild("verify_email")  
        if resultNode is not None:
            waitTimeNode = resultNode.getChild("wait_time")    
            codeMatchNode = resultNode.getChild("code_match")     
            entity.waitTime = int(str(waitTimeNode.getData(),"utf-8")) if waitTimeNode is not None else None
            entity.codeMatch =  (True if str(codeMatchNode.getData(),"utf-8")=="true" else False) if codeMatchNode is not None else None
            return entity
        else:
            return None