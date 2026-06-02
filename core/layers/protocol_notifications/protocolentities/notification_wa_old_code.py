from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .notification import NotificationProtocolEntity

class WaOldCodeNotificationProtocolEntity(NotificationProtocolEntity):
    '''
    <notification from="s.whatsapp.net" type="registration" id="2363070858" t="1695777053">
        <wa_old_registration code="420349" device_id="1kJ5TYSRRPWf_2-l7n4B4A" expiry_t="1695791453" ts="1695777053" />
    </notification>
    '''

    def __init__(self, _id,  _from, code, deviceId, timestamp, notify, offline) -> None:
        super().__init__(_id, _from, timestamp, notify, offline)
        self.code = code
        self.timestamp = timestamp
        self.deviceId = deviceId

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = NotificationProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = WaOldCodeNotificationProtocolEntity
        codeNode = node.getChild("wa_old_registration")
        entity.code = codeNode.getAttributeValue("code")
        entity.deviceId = codeNode.getAttributeValue("deviceId")
        entity.timestamp = codeNode.getAttributeValue("ts")
        return entity