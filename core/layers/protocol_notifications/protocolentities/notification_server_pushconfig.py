from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .notification import NotificationProtocolEntity
class ServerPushConfigNotificationProtocolEntity(NotificationProtocolEntity):
    '''
    <notification from="s.whatsapp.net" type="server" id="3013524925" t="1762336050">
    <push-config />
    </notification>
    '''

    def __init__(self, _id,  _from, timestamp, notify, offline) -> None:
        super().__init__("server", _id, _from, timestamp, notify, offline)        

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = NotificationProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = ServerPushConfigNotificationProtocolEntity
        return entity