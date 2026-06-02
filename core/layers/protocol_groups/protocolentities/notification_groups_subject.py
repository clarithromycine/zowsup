from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_notifications.protocolentities import NotificationProtocolEntity
from .notification_groups import GroupsNotificationProtocolEntity

class SubjectGroupsNotificationProtocolEntity(GroupsNotificationProtocolEntity):
    '''

    <notification notify="WhatsApp" id="{{id}}" t="{{TIMESTAMP}}" participant="{{PARTICIPANT_JID}}" from="{{GROUP_JID}}" type="w:gp2">
        <subject s_t="{{subject_set_timestamp}}" s_o="{{subject_owner_jid}}" subject="{{SUBJECT}}" />
    </notification>

    '''

    def __init__(self, _type, _id,  _from, timestamp, notify, participant, subject) -> None:
        super().__init__(_id, _from, timestamp, notify, participant)
        self.setSubjectData(subject)

    def setSubjectData(self, subject, subjectOwner, subjectTimestamp) -> Any:
        self.subject = subject
        self.subjectOwner = subjectOwner
        self.subjectTimestamp = int(subjectTimestamp)

    def getSubject(self) -> Any:
        return self.subject

    def getSubjectOwner(self, full = True) -> Any:
        return self.subjectOwner if full else self.subjectOwner.split('@')[0]

    def getSubjectTimestamp(self) -> Any:
        return self.subjectTimestamp

    def __str__(self):
        out = super().__str__()
        out += "New subject: %s\n" % self.getSubject()
        out += "Set by: %s\n" % self.getSubjectOwner()
        return out

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        subjectNode = ProtocolTreeNode("subject", {
            "s_t": str(self.getSubjectTimestamp()),
            "s_o": self.getSubjectOwner(),
            "subject": self.getSubject()
        })
        node.addChild(subjectNode)
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = super(SubjectGroupsNotificationProtocolEntity, SubjectGroupsNotificationProtocolEntity).fromProtocolTreeNode(node)
        entity.__class__ = SubjectGroupsNotificationProtocolEntity
        subjectNode = node.getChild("subject")
        entity.setSubjectData(subjectNode["subject"], subjectNode["s_o"], subjectNode["s_t"])
        return entity
