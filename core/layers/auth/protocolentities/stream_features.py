from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
class StreamFeaturesProtocolEntity(ProtocolEntity):
    def __init__(self,  features = None) -> None:
        super().__init__("stream:features")
        self.setFeatures(features)

    def setFeatures(self, features = None) -> Any:
        self.features = features or []

    def toProtocolTreeNode(self) -> Any:
        featureNodes = [ProtocolTreeNode(feature) for feature in self.features]
        return self._createProtocolTreeNode({}, children = featureNodes, data = None)


    @staticmethod
    def fromProtocolTreeNode(node):
        return StreamFeaturesProtocolEntity([fnode.tag for fnode in node.getAllChildren()])