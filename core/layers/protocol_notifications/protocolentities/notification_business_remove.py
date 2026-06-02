from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .notification import NotificationProtocolEntity
from proto import e2e_pb2
class BusinessRemoveNotificationProtocolEntity(NotificationProtocolEntity):
    '''
        <notification from="19392514203@s.whatsapp.net" type="business" id="504686533" offline="0" t="1740558637">
        <remove jid="19392514203@s.whatsapp.net" />
        </notification>
    '''

    def __init__(self, _id,  _from,  timestamp, notify, offline, jid) -> None:
        super().__init__("business",_id, _from, timestamp, notify, offline)
        self.jid = jid
    
    @staticmethod
    def fromProtocolTreeNode(node):
        entity = NotificationProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = BusinessRemoveNotificationProtocolEntity
        removeNode = node.getChild("remove")        
        entity.jid = removeNode.getAttributeValue("jid")
        return entity