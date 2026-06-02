from .....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
from proto import e2e_pb2
import random
from .....common import YowConstants

class GetBusinessNameIqProtocolEntity(IqProtocolEntity):

    '''
        <iq id='032' xmlns='w:biz' type='get'><verified_name jid='8801319167529@s.whatsapp.net'/></iq>
    '''

    def __init__(self, jid, _id = None) -> None:
        super().__init__("w:biz" , _id = _id, _type = "get",to="s.whatsapp.net")
        self.jid = jid
                
    def toProtocolTreeNode(self) -> Any:        
        node = super().toProtocolTreeNode()
        nameNode = ProtocolTreeNode("verified_name",{"jid":self.jid})              
        node.addChild(nameNode)
        
        return node   
    
class GetBusinessNameResultIqProtocolEntity(IqProtocolEntity):

    def __init__(self,_id=None,jid=None,verifiedLevel=None,v=None,issuer=False,name=None) -> None:
        super().__init__(_id = _id, _type = "result",to=YowConstants.DOMAIN)
        self.jid = jid
        self.verifiedLevel = verifiedLevel 
        self.v = v       
        self.issuer = issuer
        self.name = name
        self.rawVNC = None     #这个是方便直接写到文件里面        
        
    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)        
        entity.__class__ = GetBusinessNameResultIqProtocolEntity
        resultNode = node.getChild("verified_name")  
        if resultNode is not None:
            jid = resultNode.getAttributeValue("jid")    
            verifiedLevel = resultNode.getAttributeValue("verified_level")    
            v = resultNode.getAttributeValue("v")                
            rawVNC =  resultNode.getData()

            payload = e2e_pb2.VerifiedNameCertificate()                                
            payload.ParseFromString(rawVNC)
            issuer = payload.details.issuer
            name = payload.details.verifiedName
   
            entity.jid = jid
            entity.verifiedLevel = verifiedLevel
            entity.v = v
            entity.issuer = issuer
            entity.name = name
            entity.rawVNC = rawVNC
            
            return entity
        else:
            return None    




