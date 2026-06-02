from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
class ResponseProtocolEntity(ProtocolEntity):
    def __init__(self, data, xmlns = "urn:ietf:params:xml:ns:xmpp-sasl") -> None:
        super().__init__("response")
        self.xmlns = xmlns
        self.data = data
    
    def toProtocolTreeNode(self) -> Any:
        return self._createProtocolTreeNode({"xmlns": self.xmlns}, children = None, data = self.data)

    @staticmethod
    def fromProtocolTreeNode(node):
        return ResponseProtocolEntity(node.getData(), node.getAttributeValue("xmlns"))