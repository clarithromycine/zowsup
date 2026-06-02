from .....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
class SetMsgShortLinkIqProtocolEntity(IqProtocolEntity):


    '''
        <iq id='02' xmlns='w:qr' type='set'><qr code='MUM7H6LDUTY5M1' type='message' action='update'><message>Hello</message></qr></iq>
    '''
    def __init__(self, _id = None,code=None,msg=None) -> None:
        super().__init__("w:qr" , _id = _id, _type = "set")
        self.code = code
        self.msg = msg

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        qr = ProtocolTreeNode("qr",{"type":"message","action":"update","code":self.code})

        if self.msg is not None:
            message = ProtocolTreeNode("message",{},None,self.msg.encode())
            qr.addChild(message)        

        node.addChild(qr)   
        return node

class SetMsgShortLinkResultIqProtocolEntity(IqProtocolEntity):

    '''
        <iq from='16725599150@s.whatsapp.net' type='result' id='02'><qr code='MUM7H6LDUTY5M1' type='message'><message>Hello</message></qr></iq>
    '''

    def __init__(self, _id = None) -> None:
        super().__init__("w:qr" , _id = _id)
        self.code = None
        self.msg  = None
        
    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = SetMsgShortLinkResultIqProtocolEntity        
        resultNode = node.getChild("qr")          
        if resultNode is not None:            
            entity.code = resultNode.getAttributeValue("code") if resultNode is not None else None    
            messageNode = resultNode.getChild("message")
            if messageNode is not None:
                entity.msg = messageNode.getData().decode() if messageNode.getData() is not None else None
            return entity
        else:
            return None