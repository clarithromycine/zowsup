from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .notification import NotificationProtocolEntity

class ServerSyncNotificationProtocolEntity(NotificationProtocolEntity):
    '''
        <notification from='s.whatsapp.net' type='server_sync' id='1169312490' t='1767678854'>
            <collection name='critical_block' version='1'/>
            <collection name='critical_unblock_low' version='1'/>
        </notification>
    '''

    def __init__(self, _id,  _from, timestamp, notify, offline) -> None:
        super().__init__(_id, _from, timestamp, notify, offline)      
        self.collections = []               

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = NotificationProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = ServerSyncNotificationProtocolEntity
        entity.collections = []   
        for child in node.getAllChildren():
            collection = {
                "name": child.getAttributeValue("name"),
                "version": child.getAttributeValue("version")
            }
            entity.collections.append(collection)
        return entity
