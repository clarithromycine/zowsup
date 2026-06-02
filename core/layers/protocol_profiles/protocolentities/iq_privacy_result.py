from ....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_iq.protocolentities import ResultIqProtocolEntity

'''
<iq type="result" from="{{JID}}@s.whatsapp.net" id="{{IQ:ID}}">
<privacy>
<category name="last" value="all">
</category>
<category name="status" value="all">
</category>
<category name="profile" value="all">
</category>
</privacy>
</iq>
'''

class ResultPrivacyIqProtocolEntity(ResultIqProtocolEntity):
    NODE_PRIVACY="privacy"

    def __init__(self, privacy) -> None:
        super().__init__()
        self.setProps(privacy)

    def setProps(self, privacy) -> Any:
        assert type(privacy) is dict, "Privacy must be a dict {name => value}"
        self.privacy = privacy

    def __str__(self):
        out = super().__str__()
        out += "Privacy settings\n"
        for name, value in self.privacy.items():
            out += f"Category {name}  --> {value}\n"
        return out

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        queryNode = ProtocolTreeNode(self.__class__.NODE_PRIVACY)
        node.addChild(queryNode)
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = super(ResultPrivacyIqProtocolEntity, ResultPrivacyIqProtocolEntity).fromProtocolTreeNode(node)
        entity.__class__ = ResultPrivacyIqProtocolEntity
        privacyNode = node.getChild(ResultPrivacyIqProtocolEntity.NODE_PRIVACY)
        privacy = {}
        for categoryNode in privacyNode.getAllChildren():
            privacy[categoryNode["name"]] = categoryNode["value"]
        entity.setProps(privacy)
        return entity
