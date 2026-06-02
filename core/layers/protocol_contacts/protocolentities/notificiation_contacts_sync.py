from ....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .notification_contact import ContactNotificationProtocolEntity
class ContactsSyncNotificationProtocolEntity(ContactNotificationProtocolEntity):
    '''
    <notification from="4917667738517@s.whatsapp.net" t="1437251557" offline="0" type="contacts" id="4174521704">
        <sync after="1437251557"></sync>
    </notification>
    '''

    def __init__(self, _id,  _from, timestamp, notify, offline, after) -> None:
        super().__init__(_id, _from, timestamp, notify, offline)
        self.setData(after)

    def setData(self, after) -> Any:
        self.after = int(after)

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        syncNode = ProtocolTreeNode("sync", {"after": str(self.after)}, None, None)
        node.addChild(syncNode)
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = ContactNotificationProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = ContactsSyncNotificationProtocolEntity
        syncNode = node.getChild("sync")
        entity.setData(syncNode.getAttributeValue("after"))
        return entity