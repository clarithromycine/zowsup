from ....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_iq.protocolentities import ResultIqProtocolEntity
class InfoGroupsResultIqProtocolEntity(ResultIqProtocolEntity):
    '''
<iq type="result" from="{{GROUP_ID}}" id="{{IQ_ID}}">
  <group subject="{{GROUPSUBJ}}" creation="{{GROUP_CREATION_TYIME}}"
      creator="{{CREATOR_JID}}" s_t="{{SUBJECT_SET_TIMESTAMP}}" id="{{GROUP_ID}}"
      s_o="{{SUBJECT_OWNER_JID}}">
    <participant jid="{{PARTICIPANT_JID}}" type="admin" />
    <participant jid="{{PARTICIPANT_JID}}" />
    <participant jid="{{PARTICIPANT_JID}}"/>
  </group>
</iq>
    '''
    TYPE_PARTICIPANT_ADMIN = "admin"
    def __init__(self, _id, _from,
                 groupId, creationTimestamp, creatorJid,
                 subject, subjectTime, subjectOwnerJid,
                 participants) -> None:
        super().__init__(_id = _id, _from = _from)
        self.setGroupProps(groupId, creationTimestamp, creatorJid,
                           subject, subjectTime, subjectOwnerJid, participants)

    def setGroupProps(self, groupId, creationTimestamp, creatorJid,
                      subject, subjectTime, subjectOwnerJid,
                      participants) -> Any:

        assert type(participants) is dict, "Participants must be a dict {jid => type?}"

        self.groupId = groupId
        self.creationTimestamp = int(creationTimestamp)
        self.creatorJid = creatorJid
        self.subject = subject
        self.subjectTime = int(subjectTime)
        self.subjectOwnerJid = subjectOwnerJid
        self.participants = participants
        # {participant_key: lid_address} — populated by fromProtocolTreeNode
        self.participant_lids: dict = {}

    def getParticipants(self) -> Any:
        return self.participants

    def getSubject(self) -> Any:
        return self.subject

    def getGroupId(self) -> Any:
        return self.groupId

    def getCreationTimestamp(self) -> Any:
        return self.creationTimestamp

    def getCreatorJid(self, full = True) -> Any:
        return self.creatorJid if full else self.creatorJid.split('@')[0]

    def getSubjectTimestamp(self) -> Any:
        return self.subjectTime

    def getSubjectOwnerJid(self, full = True) -> Any:
        return self.subjectOwnerJid if full else self.subjectOwnerJid.split('@')[0]

    def getGroupAdmins(self, full = True) -> Any:
        admins = []
        for jid, _type in self.participants.items():
            if _type == self.__class__.TYPE_PARTICIPANT_ADMIN:
                admins.append(jid if full else jid.split('@')[0])
        return admins

    def __str__(self):
        out = super().__str__()
        out += "Group ID: {}\n".format(self.groupId)
        out += "Created: {}\n".format(self.creationTimestamp)
        out += "Creator JID: {}\n".format(self.creatorJid)
        out += "Subject: {}\n".format(self.subject)
        out += "Subject Timestamp: {}\n".format(self.subjectTime)
        out += "Subject owner JID: {}\n".format(self.subjectOwnerJid)
        out += "Participants: {}\n".format(self.participants)
        return out

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        groupNode = ProtocolTreeNode("group", {
            "subject": self.getSubject(),
            "creation": str(self.getCreationTimestamp()),
            "creator": self.getCreatorJid(),
            "s_t": self.getSubjectTimestamp(),
            "s_o": self.getSubjectOwnerJid(),
            "id": self.getGroupId()
        })

        participants = []
        for jid, _type in self.getParticipants().items():
            pnode = ProtocolTreeNode("participant", {"jid": jid})
            if _type:
                pnode["type"] = _type
            participants.append(pnode)

        groupNode.addChildren(participants)
        node.addChild(groupNode)

        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        groupNode = node.getChild("group")
        participants = {}
        participant_lids = {}  # {participant_key: lid_address e.g. 'xxx@lid'}

        addressing_mode = groupNode.getAttributeValue("addressing_mode")
        if addressing_mode == "lid":
            # LID mode: phone_number = regular JID (key), jid = LID address
            for p in groupNode.getAllChildren("participant"):
                key = p["phone_number"]
                if not key:
                    continue
                participants[key] = p["type"]
                lid = p["jid"]
                if lid:
                    participant_lids[key] = lid
        else:
            # Normal mode: jid = regular JID (key), lid attribute may exist
            for p in groupNode.getAllChildren("participant"):
                key = p["jid"]
                if not key:
                    continue
                participants[key] = p["type"]
                lid = p["lid"] if p["lid"] else None
                if lid:
                    participant_lids[key] = lid

        entity = InfoGroupsResultIqProtocolEntity(
            node["id"], node["from"],
            groupNode["id"], groupNode["creation"], groupNode["creator"], groupNode["subject"],
            groupNode["s_t"], groupNode["s_o"], participants
        )
        entity.participant_lids = participant_lids
        return entity
