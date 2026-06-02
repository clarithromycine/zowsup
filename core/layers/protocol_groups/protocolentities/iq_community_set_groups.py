from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .iq_groups import GroupsIqProtocolEntity
class SetCommunityGroupsIqProtocolEntity(GroupsIqProtocolEntity):
    '''
    <iq id="998777967160-1735831646-29" to="120363384145081882@g.us" type="set" xmlns="w:g2">
        <links>
            <link link_type="sub_group">
                <group jid="120363386166251465@g.us"/>
            </link>
        </links>
    </iq>
    '''
    def __init__(self, community_jid,group_jids, _id=None) -> None:
        super().__init__(to = community_jid, _id = _id, _type = "set")

        # group_jids 是一个数组
        self.setProps(community_jid,group_jids)

    def setProps(self, community_jid,group_jids) -> Any:
        self.community_jid = community_jid
        self.group_jids = group_jids

    def __str__(self):
        out = super().__str__()
        out += "Group JID: %s\n" % self.group_jid
        return out

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        links = ProtocolTreeNode("links",{})
        link = ProtocolTreeNode("link",{"link_type":"sub_group"})

        for jid in self.group_jids:
            group = ProtocolTreeNode("group",{"jid":jid})
            link.addChild(group)
        links.addChild(link)
        node.addChild(links)        
        return node

