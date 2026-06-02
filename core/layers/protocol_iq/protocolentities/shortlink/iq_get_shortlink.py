from .....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
class GetShortLinkIqProtocolEntity(IqProtocolEntity):


 
    '''
        <iq id='02' xmlns='w:qr' type='set'><qr type='message' action='get'/></iq>        
    '''

    def __init__(self, _id = None) -> None:
        super().__init__("w:qr" , _id = _id, _type = "set")
        
    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        qr = ProtocolTreeNode("qr",{"type":"message","action":"get"})
        node.addChild(qr)   
        return node    



class GetShortLinkResultIqProtocolEntity(IqProtocolEntity):


    '''
        <iq from='639272946168@s.whatsapp.net' type='result' id='02'><qrs><qr code='5SI4MAWM3U6XC1' type='message'/></qrs></iq>    
        
    '''

    def __init__(self, _id = None) -> None:
        super().__init__("w:qr" , _id = _id)
        self.code = None
        self.msg  = None
        
    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = GetShortLinkResultIqProtocolEntity
        resultNode = node.getChild("qrs")  
        if resultNode is not None:
            qrNode = resultNode.getChild("qr")    
            entity.code = qrNode.getAttributeValue("code") if qrNode is not None else None    

            messageNode = qrNode.getChild("message") if qrNode is not None else None
            if messageNode is not None:
                entity.msg = messageNode.getData().decode() if messageNode.getData() is not None else None

            return entity
        else:
            return None