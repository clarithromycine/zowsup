from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_notifications.protocolentities import NotificationProtocolEntity

class GroupsNotificationProtocolEntity(NotificationProtocolEntity):
    '''

    <notification notify="WhatsApp" id="{{id}}" t="1420402514" participant="{{participant_jiid}}" from="{{group_jid}}" type="w:gp2">
    </notification>

    '''

    def __init__(self, _id,  _from, timestamp, notify, participant, offline) -> None:
        super().__init__("w:gp2", _id, _from, timestamp, notify, offline)
        self.setParticipant(participant)
        self.setGroupId(_from)

    def setParticipant(self, participant) -> Any:
        self._participant = participant

    def getParticipant(self, full = True) -> Any:
        return self._participant if full else self._participant.split('@')[0]

    def getGroupId(self) -> Any:
        return self.groupId

    def setGroupId(self, groupId) -> Any:
        self.groupId = groupId


    def __str__(self):
        out = super().__str__()
        out += "Participant: %s\n" % self.getParticipant()
        return out

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        node.setAttribute("participant", self.getParticipant())
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = super(GroupsNotificationProtocolEntity, GroupsNotificationProtocolEntity).fromProtocolTreeNode(node)
        entity.__class__ = GroupsNotificationProtocolEntity
        entity.setParticipant(node.getAttributeValue("participant"))
        entity.setGroupId(node.getAttributeValue("from"))
        return entity
