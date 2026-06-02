from ....common import YowConstants
from typing import Optional, Any, List, Dict, Union
from ....structs import ProtocolEntity, ProtocolTreeNode
from .iq_groups import GroupsIqProtocolEntity
class ListGroupsIqProtocolEntity(GroupsIqProtocolEntity):
    '''
    <iq id="{{id}}"" type="get" to="g.us" xmlns="w:g2">
        <participating>
            <participants />
            <description />
        </participating">
    </iq>
    
    result (processed in iq_result_groups_list.py):
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



    def __init__(self, participants=True,_id = None) -> None:
        super().__init__(_id=_id, to = YowConstants.WHATSAPP_GROUP_SERVER, _type = "get")
        self.setProps(participants)  # 设置是否需要成员查询，默认需要

    def setProps(self, participants) -> Any:
        self.participants = participants

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()

        typeNode = ProtocolTreeNode("participating")
        if self.participants:
            participants = ProtocolTreeNode("participants")
            typeNode.addChild(participants)
        description = ProtocolTreeNode("description")
        typeNode.addChild(description)
        node.addChild(typeNode)        
        return node

