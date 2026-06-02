from ....common import YowConstants
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_iq.protocolentities import IqProtocolEntity
from ....structs import ProtocolTreeNode

class UnregisterIqProtocolEntity(IqProtocolEntity):

    XMLNS = "urn:xmpp:whatsapp:account"

    def __init__(self) -> None:
        super().__init__(_type = "get", to = YowConstants.WHATSAPP_SERVER)

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        rmNode = ProtocolTreeNode("remove", {"xmlns": self.__class__.XMLNS})
        node.addChild(rmNode)
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = UnregisterIqProtocolEntity
        removeNode = node.getChild("remove")
        assert removeNode["xmlns"] == UnregisterIqProtocolEntity.XMLNS, "Not an account delete xmlns, got %s" % removeNode["xmlns"]

        return entity