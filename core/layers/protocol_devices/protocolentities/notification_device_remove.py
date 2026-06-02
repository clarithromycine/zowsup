from ....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .notification_device import DeviceNotificationProtocolEntity
class RemoveDeviceNotificationProtocolEntity(DeviceNotificationProtocolEntity):
    '''
    <notification from="6283869786338@s.whatsapp.net" type="devices" id="331683810" t="1674392724">
    <remove device_hash="2:+e8cpGo8">
        <device jid="6283869786338.0:31@s.whatsapp.net" key-index="6" />
        <key-index-list ts="1674392047" />
    </remove>
    </notification>
    '''

    def __init__(self, _id,  _from, timestamp, deviceJid) -> None:
        super().__init__(_id, _from, timestamp)
        self.setData(deviceJid)

    def setData(self, jid) -> Any:
        self.deviceJid = jid

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = DeviceNotificationProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = RemoveDeviceNotificationProtocolEntity
        removeNode = node.getChild("remove").getChild("device")
        entity.setData(removeNode.getAttributeValue("jid"))
        return entity