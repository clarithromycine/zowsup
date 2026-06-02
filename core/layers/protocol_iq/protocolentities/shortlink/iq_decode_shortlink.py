#
#
from .....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
class DecodeShortLinkIqProtocolEntity(IqProtocolEntity):

    '''
        <iq id='09' xmlns='w:qr' type='get'><qr code='MUM7H6LDUTY5M1'/></iq>
    '''

    def __init__(self, _id = None,code=None) -> None:
        super().__init__("w:qr" , _id = _id, _type = "get")
        self.code = code
        
    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        qr = ProtocolTreeNode("qr",{"code": self.code})
        node.addChild(qr)   
        return node    


class DecodeShortLinkResultIqProtocolEntity(IqProtocolEntity):

    '''
        <iq from='16725599150@s.whatsapp.net' type='result' id='09'><qr type='message' jid='16725599150@s.whatsapp.net'><message>Hello</message><business is_signed='true' verified_name='is99zsq' verified_level='unknown'/></qr></iq>
        
    '''

    def __init__(self, _id = None) -> None:
        super().__init__("w:qr" , _id = _id)
        self.jid = None
        self.msg  = None
        self.is_signed = None
        self.verified_name = None
        self.verified_level = None

        
    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = DecodeShortLinkResultIqProtocolEntity
        qrNode = node.getChild("qr")  
        if qrNode is not None:            
            entity.jid = qrNode.getAttributeValue("jid") if qrNode is not None else None    

            messageNode = qrNode.getChild("message") if qrNode is not None else None
            if messageNode is not None:
                entity.msg = messageNode.getData().decode() if messageNode.getData() is not None else None

            businessNode = qrNode.getChild("business") if qrNode is not None else None
            if businessNode is not None:
                entity.is_signed = businessNode.getAttributeValue("is_signed")
                entity.verified_name = businessNode.getAttributeValue("verified_name")
                entity.verified_level = businessNode.getAttributeValue("verified_level")    
                
            return entity
        else:
            return None