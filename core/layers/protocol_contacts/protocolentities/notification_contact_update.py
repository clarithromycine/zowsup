from ....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .notification_contact import ContactNotificationProtocolEntity
class UpdateContactNotificationProtocolEntity(ContactNotificationProtocolEntity):
    '''
    <notification offline="0" id="{{NOTIFICATION_ID}}" notify="{{NOTIFY_NAME}}" type="contacts" 
            t="{{TIMESTAMP}}" from="{{SENDER_JID}}">
        <update jid="{{SET_JID}}"> </update>
    </notification>
    '''

    def __init__(self, _id,  _from, timestamp, notify, offline, contactJid) -> None:
        super().__init__(_id, _from, timestamp, notify, offline)
        self.setData(contactJid)

    def setData(self, jid) -> Any:
        self.contactJid = jid

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        removeNode = ProtocolTreeNode("update", {"jid": self.contactJid}, None, None)
        node.addChild(removeNode)
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = ContactNotificationProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = UpdateContactNotificationProtocolEntity
        removeNode = node.getChild("update")
        entity.setData(removeNode.getAttributeValue("jid"))
        return entity