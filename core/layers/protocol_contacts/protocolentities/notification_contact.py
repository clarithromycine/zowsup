from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_notifications.protocolentities import NotificationProtocolEntity
class ContactNotificationProtocolEntity(NotificationProtocolEntity):
    '''
    <notification offline="0" id="{{NOTIFICATION_ID}}" notify="{{NOTIFY_NAME}}" type="contacts" 
            t="{{TIMESTAMP}}" from="{{SENDER_JID}}">
    </notification>
    
    '''

    def __init__(self, _id,  _from, timestamp, notify, offline = False) -> None:
        super().__init__("contacts", _id, _from, timestamp, notify, offline)


    @staticmethod
    def fromProtocolTreeNode(node):
        entity = NotificationProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = ContactNotificationProtocolEntity
        return entity