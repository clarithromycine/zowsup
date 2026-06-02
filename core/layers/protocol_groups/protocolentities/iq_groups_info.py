from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .iq_groups import GroupsIqProtocolEntity
class InfoGroupsIqProtocolEntity(GroupsIqProtocolEntity):
    '''
    <iq id="{{id}}"" type="get" to="{{group_jid}}" xmlns="w:g2">
        <query request="interactive"></query>
    </iq>


    '''

    def __init__(self, group_jid, _id=None) -> None:
        super().__init__(to = group_jid, _id = _id, _type = "get")
        self.setProps(group_jid)

    def setProps(self, group_jid) -> Any:
        self.group_jid = group_jid

    def __str__(self):
        out = super().__str__()
        out += "Group JID: %s\n" % self.group_jid
        return out

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        node.addChild(ProtocolTreeNode("query", {"request": "interactive"}))
        return node

