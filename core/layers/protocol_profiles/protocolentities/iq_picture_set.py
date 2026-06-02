from .iq_picture import PictureIqProtocolEntity
from typing import Optional, Any, List, Dict, Union
from ....structs import ProtocolTreeNode
import time
class SetPictureIqProtocolEntity(PictureIqProtocolEntity):
    '''
    <iq type="set" id="{{id}}" xmlns="w:profile:picture", to={{jid}}">
        <picture type="image" id="{{another_id}}">
        {{Binary bytes of the picture when type is set.}}
        </picture>
    </iq>
'''
    def __init__(self, jid, previewData, pictureData, pictureId = None, _id = None,target=None) -> None:
        super().__init__(to = jid,_id= _id, type ="set",target=target)
        self.setSetPictureProps(previewData, pictureData, pictureId)

    def setSetPictureProps(self, previewData, pictureData, pictureId = None) -> Any:
        self.setPictureData(pictureData)
        self.setPictureId(pictureId or str(int(time.time())))
        self.setPreviewData(previewData)

    def setPictureData(self, pictureData) -> Any:
        self.pictureData = pictureData

    def getPictureData(self) -> Any:
        return self.pictureData

    def setPreviewData(self, previewData) -> Any:
        self.previewData = previewData

    def getPreviewData(self) -> Any:
        return self.previewData

    def setPictureId(self, pictureId) -> Any:
        self.pictureId = pictureId

    def getPictureId(self) -> Any:
        return self.pictureId

    def toProtocolTreeNode(self) -> Any:
        node = super(PictureIqProtocolEntity, self).toProtocolTreeNode()
        attribs = {"type": "image"}

        pictureNode = ProtocolTreeNode("picture", attribs, None, self.getPictureData())
        #previewNode = ProtocolTreeNode("picture", {"type": "preview"}, None, self.getPreviewData())

        node.addChild(pictureNode)
        #node.addChild(previewNode)

        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = PictureIqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = SetPictureIqProtocolEntity

        pictureNode = None
        previewNode = None

        for child in node.getAllChildren("picture"):
            nodeType = child.getAttributeValue("type")
            if nodeType == "image":
                pictureNode = child
            elif nodeType == "preview":
                previewNode = child

        entity.setSetPictureProps(previewNode.getData(), pictureNode.getData(), pictureNode.getAttributeValue("id"))
        return entity