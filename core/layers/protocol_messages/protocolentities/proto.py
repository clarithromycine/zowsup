from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
class ProtoProtocolEntity(ProtocolEntity):

    def __init__(self, protoData, mediaType = None) -> None:
        super().__init__("proto")
        self.mediaType = mediaType
        self.protoData = protoData

    def getProtoData(self) -> Any:
        return self.protoData

    def getMediaType(self) -> Any:
        return self.mediaType

    def toProtocolTreeNode(self) -> Any:
        attribs = {}
        if self.mediaType:
            attribs["mediatype"] = self.mediaType
        return ProtocolTreeNode("proto", attribs, data=self.protoData)

    @staticmethod
    def fromProtocolTreeNode(node):
        return ProtoProtocolEntity(node.data, node["mediatype"])