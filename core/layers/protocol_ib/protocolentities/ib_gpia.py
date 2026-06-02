from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .ib import IbProtocolEntity
import base64

class GpiaIbProtocolEntity(IbProtocolEntity):
    '''
    <ib>
        <gpia>
            <jws>
                XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
            </jws>
        </cat>
    </ib>
    '''
    def __init__(self, jwsdata) -> None:
        super().__init__()
        self.jwsdata = jwsdata
            
    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        jwsNode = ProtocolTreeNode("jws",data=self.jwsdata)
        gpiaNode = ProtocolTreeNode("gpia")
        gpiaNode.addChild(jwsNode)
        node.addChild(gpiaNode)
        return node

    def __str__(self):
        out = super().__str__()
        out += "ib-gpia: %s\n" % base64.b64encode(self.jwsdata)
        return out
    
class GpiaRequestIbProtocolEntity(IbProtocolEntity):
    '''
    <ib from="s.whatsapp.net">
    <gpia>
        <request nonce="AZcyZC_2NJSH41oXXFjvATD4wcDyEkGiayLU3W15MktOt3XU_1dxBdOczIellStO6RAuOrSrz_LnMsJzw3rXAKrj" />
    </gpia>
    </ib>
    '''
    def __init__(self, nonce) -> None:
        super().__init__()
        self.nonce = nonce
                
    def __str__(self):
        out = super().__str__()
        out += "ib-gpia-request: %s\n" % self.nonce
        return out


    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IbProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = GpiaRequestIbProtocolEntity
        gpiaNode = node.getChild("gpia")
        requestNode = gpiaNode.getChild("request")
        nonce = requestNode.getAttributeValue("nonce")
        entity.nonce = nonce

        return entity
