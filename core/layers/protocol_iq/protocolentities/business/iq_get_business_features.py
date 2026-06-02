from .....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
class GetBusinessFeatureIqProtocolEntity(IqProtocolEntity):

    '''
        <iq xmlns='w:biz' smax_id='139' to='s.whatsapp.net' type='get' id='0a'><features meta_verified='true' marketing_messages='true'/></iq>
    '''

    def __init__(self, _id = None) -> None:
        super().__init__("w:biz" , _id = _id, _type = "get",to="s.whatsapp.net",smax_id="139")        
                
    def toProtocolTreeNode(self) -> Any:        
        node = super().toProtocolTreeNode()
        featuresNode = ProtocolTreeNode("features",{"meta_verified":"true","marketing_messages":"true","genai":"true"})              
        node.addChild(featuresNode)
        
        return node   
    
class GetBusinessFeatureResultIqProtocolEntity(IqProtocolEntity):

    def __init__(self,_id=None) -> None:
        super().__init__(_id = _id, _type = "result",to=YowConstants.DOMAIN)
        self.marketingMessages = False
        self.metaVerified = False
        self.genai =False 
                
    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)        
        entity.__class__ = GetBusinessFeatureResultIqProtocolEntity
        mmNode = node.getChild("marketing_messages")  
        mvNode = node.getChild("meta_verified")  
        genaiNode = node.getChild("genai")

        entity.marketingMessages = True if mmNode.getAttributeValue("status")=="SUCCESS" else False
        entity.metaVerified = True if mvNode.getAttributeValue("status")=="SUCCESS" else False
        entity.genai = True if genaiNode.getAttributeValue("status")=="SUCCESS" else False
               
        return entity