from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
class WithProtoProtocolEntity(ProtocolEntity):

    def __init__(self, protoData,listNodeName) -> None:
        super().__init__("proto")        
        self.protoData = protoData
        self.mediatype = None
        self.listNodeName = listNodeName

    def getProtoData(self) -> Any:
        return self.protoData
    

    
    def getListNodeName(self) -> Any:
        return self.listNodeName


    def toProtocolTreeNode(self) -> Any:
        attribs = {"name": self.listNodeName}
        return ProtocolTreeNode("proto", attribs, data=self.protoData)

    @staticmethod
    def fromProtocolTreeNode(node):
        return WithProtoProtocolEntity(node.data, node["name"])