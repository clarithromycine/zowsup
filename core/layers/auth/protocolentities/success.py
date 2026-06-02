from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
class SuccessProtocolEntity(ProtocolEntity):
    def __init__(self, creation, props, t, location, lid) -> None:
        super().__init__("success")
        self.location = location
        self.creation = int(creation)
        self.props = props
        self.lid = lid
        self.t = int(t) ##whatever that is !

    def __str__(self):
        out  = "Account:\n"
        out += "Location: %s\n" % self.location
        out += "Creation: %s\n" % self.creation
        out += "Props: %s\n" % self.props
        out += "t: %s\n" % self.t
        out += "Lid: %s\n" % self.lid
        return out

    def toProtocolTreeNode(self) -> Any:
        attributes = {
            "location"      :  self.location,
            "creation"    :    str(self.creation),
            "props"       :    self.props,
            "t"           :    str(self.t),
            "lid": self.lid
        }
        return self._createProtocolTreeNode(attributes)

    @staticmethod
    def fromProtocolTreeNode(node):
        return SuccessProtocolEntity(
            node.getAttributeValue("creation"),
            node.getAttributeValue("props"),
            node.getAttributeValue("t"),
            node.getAttributeValue("location"),
            node.getAttributeValue("lid")
            )