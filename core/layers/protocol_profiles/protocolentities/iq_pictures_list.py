from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .iq_picture import PictureIqProtocolEntity
class ListPicturesIqProtocolEntity(PictureIqProtocolEntity):
    '''
    <iq type="get" id="{{id}}" xmlns="w:profile:picture", to="self.jid">
        <list>
            <user jid="{{user_jid}}"></user>
            <user jid="{{user_jid}}"></user>
        </list>
    </iq>
    '''

    def __init__(self, selfJid, jids) -> None:
        super().__init__(jid = selfJid, type = "get")
        self.setProps(jids)

    def setProps(self, jids) -> Any:
        assert type(jids) is list and len(jids), "Must specify a list of jids to get the pictures for"
        self.jids = jids

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        userNodes = [ProtocolTreeNode("user", {"jid": jid}) for jid in self.jids]
        listNode = ProtocolTreeNode("list", {}, userNodes)
        node.addChild(listNode)
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = PictureIqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = ListPicturesIqProtocolEntity
        jids = [userNode.getAttributeValue("jid") for userNode in node.getChild("list").getAllChildren()]
        entity.setProps(jids)
        return entity