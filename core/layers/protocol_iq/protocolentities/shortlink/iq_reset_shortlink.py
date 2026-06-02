from .....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
class ResetShortLinkIqProtocolEntity(IqProtocolEntity):


    '''
        <iq id='04' xmlns='w:qr' type='set'><qr type='message' action='revoke'/></iq>
    '''

    def __init__(self, _id = None) -> None:
        super().__init__("w:qr" , _id = _id, _type = "set")
        
    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        qr = ProtocolTreeNode("qr",{"type":"message","action":"revoke"})
        node.addChild(qr)   
        return node    


class ResetShortLinkResultIqProtocolEntity(IqProtocolEntity):

    '''
        <iq from='16725599150@s.whatsapp.net' type='result' id='04'><qr code='ETHJ4B4K3QWAK1' type='message'/></iq>        
    '''

    def __init__(self, _id = None) -> None:
        super().__init__("w:qr" , _id = _id)
        self.code = None
        
    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = ResetShortLinkResultIqProtocolEntity        
        resultNode = node.getChild("qr")          
        if resultNode is not None:            
            entity.code = resultNode.getAttributeValue("code") if resultNode is not None else None    
            return entity
        else:
            return None