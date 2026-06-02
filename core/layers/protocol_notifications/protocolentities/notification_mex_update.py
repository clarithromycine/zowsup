from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .notification import NotificationProtocolEntity

class MexUpdateNotificationProtocolEntity(NotificationProtocolEntity):
    '''
    <notification from="s.whatsapp.net" type="mex" id="355574974" t="1729559459">
        <update op_name="NotificationUserReachoutTimelockUpdate">
            0x7b2264617461223a7b22787761325f6e6f746966795f6163636f756e745f72656163686f75745f74696d656c6f636b223a7b2269735f616374697665223a747275652c2274696d655f656e666f7263656d656e745f656e6473223a2231373239353831303539227d7d7d
        </update>
    </notification>
    '''

    def __init__(self, _id,  _from, opName, jsonObj, timestamp, notify, offline) -> None:
        super().__init__(_id, _from, timestamp, notify, offline)
        self.opName = opName
        self.jsonObj = jsonObj

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = NotificationProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = MexUpdateNotificationProtocolEntity
        updateNode = node.getChild("update")
        entity.opName = updateNode.getAttributeValue("op_name")
        entity.jsonObj = updateNode.getData().decode()
        return entity