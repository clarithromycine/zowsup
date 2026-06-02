from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .ib import IbProtocolEntity
import base64

class SafetynetIbProtocolEntity(IbProtocolEntity):
    '''
    <ib>
        <integrity_payload>
                XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        </integrity_payload>
    </ib>
    '''
    def __init__(self, payload) -> None:
        super().__init__()
        self.payload = payload
            
    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        payloadNode = ProtocolTreeNode("integrity_payload",data=self.payload)
        node.addChild(payloadNode)
        return node

    def __str__(self):
        out = super().__str__()
        out += "ib-safetynet: %s\n" % base64.b64encode(self.payload)
        return out


class SafetynetRequestIbProtocolEntity(IbProtocolEntity):
    '''
    <ib from="s.whatsapp.net">
    <safetynet>
        <integrity nonce="ATbBMzYi88_0kA_2FfuFQM_q2bptUXbS6ZxAQMezC0bHiRunBmCMINjnsi3KDTXzoqewJMXHRakz77289SVMOdKQ" />
    </safetynet>
    </ib>
    '''
    def __init__(self, nonce) -> None:
        super().__init__()
        self.nonce = nonce
                
    def __str__(self):
        out = super().__str__()
        out += "ib-safetynet-request: %s\n" % self.nonce
        return out

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IbProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = SafetynetRequestIbProtocolEntity
        safetynetNode = node.getChild("safetynet")
        integrityNode = safetynetNode.getChild("integrity")
        nonce = integrityNode.getAttributeValue("nonce")
        entity.nonce = nonce
        return entity