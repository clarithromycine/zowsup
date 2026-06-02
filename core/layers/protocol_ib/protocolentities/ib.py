from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
class IbProtocolEntity(ProtocolEntity):
    '''
    <ib></ib>
    '''
    def __init__(self,to=None) -> None:
        super().__init__("ib")
        self.to = to
    
    def toProtocolTreeNode(self) -> Any:

        attribs = {}
        if self.to :
            attribs["to"] = self.to

        return self._createProtocolTreeNode(attribs, None, None)

    def __str__(self):
        out  = "Ib:\n"
        return out

    @staticmethod
    def fromProtocolTreeNode(node):
        return IbProtocolEntity()
