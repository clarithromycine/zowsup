from ....layers.protocol_iq.protocolentities.iq import IqProtocolEntity
from typing import Optional, Any, List, Dict, Union
from ....structs.protocoltreenode import ProtocolTreeNode
class LastseenIqProtocolEntity(IqProtocolEntity):
    XMLNS = "jabber:iq:last"
    def __init__(self, jid, _id = None) -> None:
        super().__init__(self.__class__.XMLNS, _type = "get", to = jid, _id = _id)

    @staticmethod
    def fromProtocolTreeNode(node):
        return LastseenIqProtocolEntity(node["to"])

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        node.setAttribute("xmlns", self.__class__.XMLNS)
        node.addChild(ProtocolTreeNode("query"))
        return node
