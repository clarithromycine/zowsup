from ....common import YowConstants
from typing import Optional, Any, List, Dict, Union
from ....structs import ProtocolEntity, ProtocolTreeNode
from .iq_groups import GroupsIqProtocolEntity
import random
import uuid
class CreateCommunityIqProtocolEntity(GroupsIqProtocolEntity):
    '''
    <iq type="set" id="{{id}}" xmlns="w:g2" to="g.us">
        <create subject="{{subject}}">
             <participant jid="{{jid}}" />
        </create>
    </iq>
    '''

    def __init__(self, subject, _id = None, participants = None,creator = None) -> None:
        super().__init__(to = YowConstants.WHATSAPP_GROUP_SERVER, _id = _id, _type = "set")
        self.setProps(subject,creator)
        self.setParticipants(participants or [])

    def setProps(self, subject,creator) -> Any:
        self.subject = subject
        if '@' in creator :
            creator = creator.split("@")[0]        
        self.creator = creator


    def setParticipants(self, participants) -> Any:
        self.participantList = participants

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        cnode = ProtocolTreeNode("create",{
                                     "subject":self.subject                                     
                                  })
        #participantNodes = [
        #    ProtocolTreeNode("participant", {   
        #        "jid":participant
        #    })                
        #    for participant in self.participantList
        #]

        #默认群组设置：只有管理员可以配置群组信息，只有管理员可以发言，只有管理员可以添加成员
        #如需要其它的，后续可以通过setGroup指令修改
        #cnode.addChildren(participantNodes)        
        #cnode.addChild(ProtocolTreeNode("announcement",{}))        
        #cnode.addChild(ProtocolTreeNode("locked",{}))        

        desc = ProtocolTreeNode("description",{"id":"112233445566112233445566"})
        desc.addChild(ProtocolTreeNode("body",{},None,b"SECRET"))
        cnode.addChild(desc) 
        cnode.addChild(ProtocolTreeNode("parent",{"default_membership_approval_mode":"request_required"})) 
        cnode.addChild(ProtocolTreeNode("create_general_chat",{})) 
        cnode.addChild(ProtocolTreeNode("allow_non_admin_sub_group_creation",{}))        
        node.addChild(cnode)
        
        return node

    
