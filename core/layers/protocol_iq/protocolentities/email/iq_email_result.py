from .....structs import  ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
from .....common import YowConstants

class EmailResultIqProtocolEntity(IqProtocolEntity):

    def __init__(self,_id=None,emailAddress=None,verified=None,confirmed=False,doVerify=False) -> None:
        super().__init__(_id = _id, _type = "result",to=YowConstants.DOMAIN)
        self.emailAddress = emailAddress
        self.verified = verified 
        self.confirmed = confirmed       
        self.doVerify = doVerify

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = EmailResultIqProtocolEntity
        resultNode = node.getChild("email")  
        if resultNode is not None:
            addrNode = resultNode.getChild("email_address")    
            verifiedNode = resultNode.getChild("verified")     
            confirmedNode = resultNode.getChild("confirmed")  
            doVerifyNode = resultNode.getChild("do_verify")  
            
            entity.emailAddress = str(addrNode.getData(),"utf-8") if addrNode is not None else None
            entity.verified =  (True if str(verifiedNode.getData(),"utf-8")=="true" else False) if verifiedNode is not None else None   
            entity.confirmed =  (True if str(confirmedNode.getData(),"utf-8")=="true" else False) if confirmedNode is not None else None
            entity.doVerify =  (True if str(doVerifyNode.getData(),"utf-8")=="true" else False)  if doVerifyNode is not None else None           
            return entity
        else:
            return None   





        


