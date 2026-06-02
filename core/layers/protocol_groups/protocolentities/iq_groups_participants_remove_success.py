from ....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_iq.protocolentities import ResultIqProtocolEntity
class SuccessRemoveParticipantsIqProtocolEntity(ResultIqProtocolEntity):
    '''
    <iq type="result" from="{{group_jid}}" id="{{id}}">
        <remove type="success" participant="{{jid}}" />
        <remove type="success" participant="{{jid}}"/>
    </iq>
    '''

    def __init__(self, _id, groupId, participantList) -> None:
        super().__init__(_from = groupId, _id = _id)
        self.setProps(groupId, participantList)

    def setProps(self, groupId, participantList) -> Any:
        self.groupId = groupId
        self.participantList = participantList
        self.action = 'remove'

    def getAction(self) -> Any:
        return self.action

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        participantNodes = [
            ProtocolTreeNode("remove", {
                "type":                     "success",
                "participant":       participant
            })
            for participant in self.participantList
        ]
        node.addChildren(participantNodes)

        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = ResultIqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = SuccessRemoveParticipantsIqProtocolEntity
        participantList = []
        for participantNode in node.getAllChildren():
            if participantNode["type"]=="success":
                participantList.append(participantNode["participant"])
        entity.setProps(node.getAttributeValue("from"), participantList)
        return entity
