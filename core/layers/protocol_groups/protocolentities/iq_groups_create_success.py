from ....common import YowConstants
from typing import Optional, Any, List, Dict, Union
from ....structs import ProtocolTreeNode
from ....layers.protocol_iq.protocolentities import ResultIqProtocolEntity
class SuccessCreateGroupsIqProtocolEntity(ResultIqProtocolEntity):
    '''
    <iq type="result" id="{{id}}" from="g.us">
        <group id="{group_id}"></group>
    </iq>
    '''

    def __init__(self, _id, groupId) -> None:
        super().__init__(_from = YowConstants.WHATSAPP_GROUP_SERVER, _id = _id)
        self.setProps(groupId)

    def setProps(self, groupId) -> Any:
        self.groupId = groupId

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        node.addChild(ProtocolTreeNode("group",{"id": self.groupId}))
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = ResultIqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = SuccessCreateGroupsIqProtocolEntity
        entity.setProps(node.getChild("group").getAttributeValue("id"))
        return entity
