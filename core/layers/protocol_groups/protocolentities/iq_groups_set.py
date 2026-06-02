from ....common import YowConstants
from typing import Optional, Any, List, Dict, Union
from ....structs import ProtocolEntity, ProtocolTreeNode
from .iq_groups import GroupsIqProtocolEntity
class SetGroupsIqProtocolEntity(GroupsIqProtocolEntity):
    '''
    <iq id="{{id}}"" type="set" to="{{group_jid}}" xmlns="w:g2">

        以下n选1
        <announcement />|<not_announcement />
        <locked />|<unlocked />
        <member_add_mode>...</member_add_mode>
        <membership_approval_mode>...</membership_approval_mode>
    </iq>
    '''

    def __init__(self, group_jid,action,value=None) -> None:
        super().__init__(to = group_jid, _type = "set")
        self.action = action
        self.value = value


    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()              
        if self.value is None:
            anode = ProtocolTreeNode(self.action,{})
            node.addChild(anode)
    
        elif self.action=="member_add_mode":
            anode = ProtocolTreeNode(self.action,{},None,self.value.encode())
            node.addChild(anode)            
    
        elif self.action=="membership_approval_mode":
            modeNode =  ProtocolTreeNode("group_join",{"state":self.value})
            anode = ProtocolTreeNode(self.action,{},[modeNode])
            node.addChild(anode)
                                
        return node


