from .iq_picture import PictureIqProtocolEntity
from typing import Optional, Any, List, Dict, Union
from ....structs import ProtocolTreeNode
class ResultGetPictureIqProtocolEntity(PictureIqProtocolEntity):
    '''
    <iq type="result" from="{{jid}}" id="{{id}}">
        <picture type="image | preview" id="{{another_id}}", url="...." />                
    </iq>
    '''
    def __init__(self, jid,  pictureId, type, url, _id = None) -> None:
        super().__init__(jid, _id, "result")
        self.setResultPictureProps( pictureId, type, url)

    def setResultPictureProps(self,  pictureId, type,url) -> Any:
        self.url = url                
        self.type = type
        self.pictureId = pictureId

    def getPictureId(self) -> Any:
        return self.pictureId
    
    def getPictureType(self) -> Any:
        return self.type
    
    def getUrl(self) -> Any:
        return self.url

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = PictureIqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = ResultGetPictureIqProtocolEntity
        pictureNode = node.getChild("picture")
        entity.setResultPictureProps(pictureNode.getAttributeValue("id"), pictureNode.getAttributeValue("type"),pictureNode.getAttributeValue("url"))
        return entity