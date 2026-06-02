from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_notifications.protocolentities import NotificationProtocolEntity
class DeviceNotificationProtocolEntity(NotificationProtocolEntity):
    '''
    <notification  id="{{NOTIFICATION_ID}}"  type="contacts" 
            t="{{TIMESTAMP}}" from="{{SENDER_JID}}">
    </notification>
    
    '''

    def __init__(self, _id,  _from, timestamp, notify, offline = False) -> None:
        super().__init__("devices", _id, _from, timestamp)


    @staticmethod
    def fromProtocolTreeNode(node):
        entity = NotificationProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = DeviceNotificationProtocolEntity
        return entity