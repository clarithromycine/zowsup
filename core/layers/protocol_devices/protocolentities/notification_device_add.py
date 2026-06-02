from ....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .notification_device import DeviceNotificationProtocolEntity
class AddDeviceNotificationProtocolEntity(DeviceNotificationProtocolEntity):
    '''
    <notification from="6283869786338@s.whatsapp.net" type="devices" id="2500674566" t="1674394794">
    <add device_hash="2:ww16Ea/Y">
        <device jid="6283869786338.0:32@s.whatsapp.net" key-index="7" />
        <key-index-list ts="1674394789">
        0x0a1308f1f192f60210a5f9b49e061807220300010712404c31ba28b050eebffa3cf66ab7ad7964d2c7bf2a4cd7c0dfc2a89cbec91dbb2e2c3006367bcacc9c42157b063bd7a1514b5cd15f8e6abb1e9c87aaa378366104
        </key-index-list>
    </add>
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
        entity.__class__ = AddDeviceNotificationProtocolEntity
        addNode = node.getChild("add").getChild("device")
        entity.setData(addNode.getAttributeValue("jid"))
        return entity