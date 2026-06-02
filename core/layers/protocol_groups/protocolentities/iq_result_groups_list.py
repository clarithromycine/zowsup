from ....common import YowConstants
from typing import Optional, Any, List, Dict, Union
from ....structs import ProtocolEntity, ProtocolTreeNode
from ....layers.protocol_iq.protocolentities import ResultIqProtocolEntity
from ..structs import Group
class ListGroupsResultIqProtocolEntity(ResultIqProtocolEntity):
    '''
    <iq type="result" from="g.us" id="{{IQ_ID}}">
      <groups>
          <group s_t="{{SUBJECT_TIME}}" creation="{{CREATING_TIME}}" creator="{{OWNER_JID}}" id="{{GROUP_ID}}" s_o="{{SUBJECT_OWNER_JID}}" subject="{{SUBJECT}}">
            <participant jid="{{JID}}" type="admin">
            </participant>
            <participant jid="{{JID}}">
            </participant>
          </group>
          <group s_t="{{SUBJECT_TIME}}" creation="{{CREATING_TIME}}" creator="{{OWNER_JID}}" id="{{GROUP_ID}}" s_o="{{SUBJECT_OWNER_JID}}" subject="{{SUBJECT}}">
            <participant jid="{{JID}}" type="admin">
            </participant>
          </group>
      <groups>
    </iq>
    '''

    def __init__(self, groupsList) -> None:
        super().__init__(_from = YowConstants.WHATSAPP_GROUP_SERVER)
        self.setProps(groupsList)

    def __str__(self):
        out = super().__str__()
        out += "Groups:\n"
        for g in self.groupsList:
            out += "%s\n" % g
        return out

    def getGroups(self) -> Any:
        return self.groupsList

    def setProps(self, groupsList) -> Any:
        assert type(groupsList) is list and (len(groupsList) == 0 or groupsList[0].__class__ is Group),\
            "groupList must be a list of Group instances"
        self.groupsList = groupsList


    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()

        groupsNodes = []
        for group in self.groupsList:
            groupNode = ProtocolTreeNode("group", {
                "id":       group.getId(),
                "creator":    group.getCreator(),
                "subject":  group.getSubject(),
                "s_o":      group.getSubjectOwner(),
                "s_t":      str(group.getSubjectTime()),
                "creation": str(group.getCreationTime())
                },
            )
            participants = []
            for jid, _type in group.getParticipants().items():
                pnode = ProtocolTreeNode("participant", {"jid": jid})
                if _type:
                    pnode["type"] = _type
                participants.append(pnode)
            groupNode.addChildren(participants)
            groupsNodes.append(groupNode)

        node.addChild(ProtocolTreeNode("groups", children = groupsNodes))
        return node

    @staticmethod
    def fromProtocolTreeNode(node):        
        entity = ResultIqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = ListGroupsResultIqProtocolEntity
        groups = []                       
        for groupNode in node.getChild("groups").getAllChildren():            
            participants = {}
            for p in groupNode.getAllChildren("participant"):
                participants[p["jid"]] = p["type"]
            groups.append(
                Group(groupNode["id"], groupNode["creator"], groupNode["subject"], groupNode["s_o"], groupNode["s_t"], groupNode["creation"], participants)
            )
        entity.setProps(groups)        
        return entity
