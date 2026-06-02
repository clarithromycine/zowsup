from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .ib import IbProtocolEntity
import base64

class CatIbProtocolEntity(IbProtocolEntity):
    '''
    <ib>
        <cat>
          XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        </cat>
    </ib>

    cat for "client auth token"
    
    '''
    def __init__(self, catdata) -> None:
        super().__init__()
        self.catdata = catdata
            
    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        catNode = ProtocolTreeNode("cat",data=self.catdata)
        node.addChild(catNode)
        return node

    def __str__(self):
        out = super().__str__()
        out += "ib-cat: %s\n" % base64.b64encode(self.catdata)
        return out
