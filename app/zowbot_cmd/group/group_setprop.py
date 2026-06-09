"""misc.reachouttimelock command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_groups.protocolentities.iq_groups_set import SetGroupsIqProtocolEntity
from core.layers.protocol_iq.protocolentities import WmexQueryIqProtocolEntity, WmexResultIqProtocolEntity
from core.layers.protocol_iq.protocolentities.iq_result import ResultIqProtocolEntity

logger = logging.getLogger(__name__)


class Cmd_Group_SetProp(BotCommand):


    COMMAND = "group.setprop"
    DESCRIPTION = "Set group properties"


    async def execute(self, params, options):
        """
        Set group properties.
        
        Returns: dict with the result of the operation
        
        Previous location: ZowBotLayer.setGroupProperties()
                
        params:  groupJid, propertyName, propertyValue

        "member_link_mode":ADMIN_LINK/ALL_MEMBER_LINK  是否允许通过QRCODE或者邀请链接加入群
        "member_add_mode":ADMIN_ADD/ALL_MEMBER_ADD     是否允许群成员邀请好友加入群
        "member_share_group_history_mode":ADMIN_SHARE/ALL_MEMBER_SHARE  是否允许群成员查看加入群之前的聊天记录

                
        "lock"/"unlock": None     是否允许Edit group Settings，锁定后只有管理员可以修改群信息, value为None即可
        "announcement"/"not_announcement: None  是否允许群内发送信息，true为只有管理员可发，false为所有人可发，value为None即可
        "membership_approval_mode": "on"/"off"  是否开启加群审批，true为需要管理员审批，false为不需要审批
        """

        try:
            if params[0].find("@g.us") == -1:
                params[0] = params[0]+"@g.us"

            if params[1] not in ["member_link_mode","member_add_mode","member_share_group_history_mode","lock","announcement","group_join_approval"]:
                raise ValueError("Invalid property name. Allowed values are: member_link_mode, member_add_mode, member_share_group_history_mode, lock, announcement, group_join_approval")



            if params[1] in ["member_link_mode","member_add_mode","member_share_group_history_mode"]
                query_obj = {
                    "variables": {
                        "groupJid": params[0],
                        "input": {}
                    }
                }

                query_obj["variables"]["input"][params[1]] = params[2]
                entity = WmexQueryIqProtocolEntity(
                    query_name="SetGroupProperty",
                    query_obj=query_obj
                )
                result = await self.send_iq_expect(entity, WmexResultIqProtocolEntity)
                print(result.result_obj)

                return self.success(result=result.result_obj)
            
            else:
                entity = SetGroupsIqProtocolEntity(groupJid=params[0], propertyName=params[1], propertyValue=params[2] if len(params)>2 else None) 
                result = await self.send_iq_expect(entity, ResultIqProtocolEntity)
                return self.success()
                        
        except Exception as e:
            logger.error(f"{self.COMMAND} error: {e}")
            return self.fail(error=str(e))   


