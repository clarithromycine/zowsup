from ....layers.protocol_iq.protocolentities import IqProtocolEntity
from typing import Optional, Any, List, Dict, Union
from ....structs import ProtocolTreeNode

'''
<iq xmlns="privacy" type="get" id="{{IQ_ID}}">
<privacy>
</privacy>
</iq>
'''

class GetPrivacyIqProtocolEntity(IqProtocolEntity):
    XMLNS = "privacy"
    def __init__(self) -> None:
        super().__init__(self.__class__.XMLNS, _type="get")

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        queryNode = ProtocolTreeNode(self.__class__.XMLNS)
        node.addChild(queryNode)
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        assert node.getChild(GetPrivacyIqProtocolEntity.XMLNS) is not None, "Not a get privacy iq node %s" % node
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = GetPrivacyIqProtocolEntity
        return entity
