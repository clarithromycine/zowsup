from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .notification_picture import PictureNotificationProtocolEntity
class SetPictureNotificationProtocolEntity(PictureNotificationProtocolEntity):
    '''
    <notification offline="0" id="{{NOTIFICATION_ID}}" notify="{{NOTIFY_NAME}}" type="picture" 
            t="{{TIMESTAMP}}" from="{{SENDER_JID}}">
        <set jid="{{SET_JID}}" id="{{SET_ID}}">
        </set>
    </notification>
    '''

    def __init__(self, _id,  _from, status, timestamp, notify, offline, setJid, setId) -> None:
        super().__init__(_id, _from, timestamp, notify, offline)
        self.setData(setJid, setId)

    def setData(self, setJid, setId) -> Any:
        self.setId  =    setId
        self.setJid =   setJid
    
    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        setNode = ProtocolTreeNode("set", {"jid": self.setJid, "id": self.setId}, None, None)
        node.addChild(setNode)
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = PictureNotificationProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = SetPictureNotificationProtocolEntity
        setNode = node.getChild("set")
        entity.setData(setNode.getAttributeValue("jid"), setNode.getAttributeValue("id"))
        return entity