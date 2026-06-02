from .iq_picture import PictureIqProtocolEntity
from typing import Optional, Any, List, Dict, Union
from ....structs import ProtocolTreeNode
from ....layers.protocol_iq.protocolentities import IqProtocolEntity
from ....common import YowConstants

class GetPictureIqProtocolEntity(IqProtocolEntity):
    '''
    <iq type="get" id="{{id}}" xmlns="w:profile:picture", to="s.whatsapp.net" target="{{jid}}">
        <picture type="image | preview" query="url" />
    </iq>'''
    def __init__(self, jid, preview = True, _id = None) -> None:
        super().__init__(xmlns="w:profile:picture",_type="get",to=YowConstants.WHATSAPP_SERVER)
        self.setGetPictureProps(jid,preview)

    def setGetPictureProps(self, jid, preview = True) -> Any:
        self.preview = preview
        self.jid = jid

    def isPreview(self) -> Any:
        return self.preview

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        node.setAttribute("target",self.jid)
        pictureNode = ProtocolTreeNode("picture", {"type": "preview" if self.isPreview() else "image" ,"query":"url"})
        node.addChild(pictureNode)
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = PictureIqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = GetPictureIqProtocolEntity
        entity.setGetPictureProps(node.getChild("picture").getAttributeValue("type"))
        return entity