from ...layers import YowLayer, YowLayerEvent, YowProtocolLayer
from typing import Optional, Any, List, Dict, Union
from ...layers.protocol_iq.protocolentities import ErrorIqProtocolEntity
from ...layers.protocol_iq.protocolentities.iq_result import ResultIqProtocolEntity
from .protocolentities import *
import logging
logger = logging.getLogger(__name__)


class YowGroupsProtocolLayer(YowProtocolLayer):

    HANDLE = (
        CreateGroupsIqProtocolEntity,
        InfoGroupsIqProtocolEntity,
        LeaveGroupsIqProtocolEntity,
        ListGroupsIqProtocolEntity,
        SubjectGroupsIqProtocolEntity,
        ParticipantsGroupsIqProtocolEntity,
        AddParticipantsIqProtocolEntity,
        PromoteParticipantsIqProtocolEntity,
        DemoteParticipantsIqProtocolEntity,
        RemoveParticipantsIqProtocolEntity,
        JoinWithCodeGroupsIqProtocolEntity,        
        SetGroupsIqProtocolEntity,
        ApproveParticipantsGroupsIqProtocolEntity,
        GetInviteCodeGroupsIqProtocolEntity
    )

    def __init__(self) -> None:
        handleMap = {
            "iq": (self.recvIq, self.sendIq),
            "notification": (self.recvNotification, None)
        }
        super().__init__(handleMap)

    def __str__(self):
        return "Groups Iq Layer"
    
    async def recvIq(self, node) -> Any:        
        if node["type"] == "result":
            rNode = node.getChild(0)
            if rNode is None:
                # process in protocol_iq
                pass
            elif rNode.tag=="groups":
                #listgroup
                await self.toUpper(ListGroupsResultIqProtocolEntity.fromProtocolTreeNode(node))

            elif rNode.tag=="group":
                #groupinfo or creategroup or join 都是这个结构
                if node["from"].endswith("@g.us"):
                    await self.toUpper(InfoGroupsResultIqProtocolEntity.fromProtocolTreeNode(node))
                elif node["from"].endswith("g.us"):
                    if rNode["jid"] is not None:
                        await self.toUpper(SuccessJoinWithCodeGroupsIqProtocolEntity.fromProtocolTreeNode(node))
                    elif rNode["id"] is not None:
                        await self.toUpper(SuccessCreateGroupsIqProtocolEntity.fromProtocolTreeNode(node))
                    else:
                        logger.warning("unknown group result node, please complete the process-branch")
            elif rNode.tag=="add":
                await self.toUpper(SuccessAddParticipantsIqProtocolEntity.fromProtocolTreeNode(node))
            elif rNode.tag=="remove":
                await self.toUpper(SuccessRemoveParticipantsIqProtocolEntity.fromProtocolTreeNode(node))
            elif rNode.tag=="promote":
                await self.toUpper(ResultIqProtocolEntity.fromProtocolTreeNode(node))
            elif rNode.tag=="demote":
                await self.toUpper(ResultIqProtocolEntity.fromProtocolTreeNode(node))
            elif rNode.tag=="leave":
                await self.toUpper(SuccessLeaveGroupsIqProtocolEntity.fromProtocolTreeNode(node))
            elif rNode.tag=="invite":
                await self.toUpper(SuccessGetInviteCodeGroupsIqProtocolEntity.fromProtocolTreeNode(node))
            elif rNode.tag in ["locked","unlocked","announcement","not_announcement","membership_approval_mode","membership_requests_action"]:
                await self.toUpper(ResultIqProtocolEntity.fromProtocolTreeNode(node))
    
    async def sendIq(self, entity) -> Any:        
        if entity.getXmlns() == "w:g2":      
            node = entity.toProtocolTreeNode()            
            await self.toLower(node)  

    async def recvNotification(self, node) -> Any:     
        if node["type"] == "w:gp2":    
            rNode = node.getChild(0)
            if rNode.tag == "subject":                   
                await self.toUpper(SubjectGroupsNotificationProtocolEntity.fromProtocolTreeNode(node))
            elif rNode.tag == "create":
                if rNode["reason"] is not None:
                    await self.toUpper(InviteGroupsNotificationProtocolEntity.fromProtocolTreeNode(node))
                else:
                    await self.toUpper(CreateGroupsNotificationProtocolEntity.fromProtocolTreeNode(node))
            elif rNode.tag =="remove":
                await self.toUpper(RemoveGroupsNotificationProtocolEntity.fromProtocolTreeNode(node))
            elif rNode.tag == "add":
                await self.toUpper(AddGroupsNotificationProtocolEntity.fromProtocolTreeNode(node))


    # 还剩设置主题和设置描述两个接口还没完善








