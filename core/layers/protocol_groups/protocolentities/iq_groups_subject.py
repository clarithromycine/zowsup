from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .iq_groups import GroupsIqProtocolEntity
class SubjectGroupsIqProtocolEntity(GroupsIqProtocolEntity):
    '''
    <iq type="set" id="{{id}}" xmlns="w:g2", to={{group_jid}}">
        <subject>
              {{NEW_VAL}}
        </subject>
    </iq>
    '''
    def __init__(self, jid, subject, _id = None) -> None:
        super().__init__(to = jid, _id = _id, _type = "set")
        self.setProps(subject)

    def setProps(self, subject) -> Any:
        self.subject = subject

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        node.addChild(ProtocolTreeNode("subject",{}, None, self.subject))
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = super(SubjectGroupsIqProtocolEntity, SubjectGroupsIqProtocolEntity).fromProtocolTreeNode(node)
        entity.__class__ = SubjectGroupsIqProtocolEntity
        entity.setProps(node.getChild("subject").getData())
        return entity
