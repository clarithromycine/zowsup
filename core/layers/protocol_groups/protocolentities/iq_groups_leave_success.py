from ....common import YowConstants
from typing import Optional, Any, List, Dict, Union
from ....structs import ProtocolTreeNode
from ....layers.protocol_iq.protocolentities import ResultIqProtocolEntity


class SuccessLeaveGroupsIqProtocolEntity(ResultIqProtocolEntity):
    '''
    <iq type="result" from="g.us" id="{{ID}}">
        <leave>
            <group id="{{GROUP_JID}}"></group>
        </leave>
    </iq>
    '''

    def __init__(self, _id, groupId) -> None:
        super().\
            __init__(_from=YowConstants.WHATSAPP_GROUP_SERVER, _id=_id)
        self.setProps(groupId)

    def setProps(self, groupId) -> Any:
        self.groupId = groupId

    def __str__(self):
        out = super().__str__()
        out += "Group Id: %s\n" % self.groupId
        return out

    def toProtocolTreeNode(self) -> Any:
        node = super().\
            toProtocolTreeNode()
        leaveNode = ProtocolTreeNode(
            "leave", {}, [ProtocolTreeNode("group", {"id": self.groupId})]
        )
        node.addChild(leaveNode)
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = super(SuccessLeaveGroupsIqProtocolEntity, SuccessLeaveGroupsIqProtocolEntity).fromProtocolTreeNode(node)
        entity.__class__ = SuccessLeaveGroupsIqProtocolEntity
        entity.setProps(
            node.getChild("leave").getChild("group").getAttributeValue("id")
        )
        return entity
