from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .iq_groups import GroupsIqProtocolEntity
class GetInviteCodeGroupsIqProtocolEntity(GroupsIqProtocolEntity):
    '''
    <iq type="get" id="{{id}}" xmlns="w:g2", to={{group_jid}}">
        <invite/>                      
    </iq>
    '''
    def __init__(self, group_jid, _id = None) -> None:
        super().__init__(to = group_jid, _id = _id, _type = "get")        

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        node.addChild(ProtocolTreeNode("invite",{}, None, None))
        return node
