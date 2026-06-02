from .iq_picture import PictureIqProtocolEntity
from typing import Optional, Any, List, Dict, Union

class ResultSetPictureIqProtocolEntity(PictureIqProtocolEntity):
    '''
    <iq type="result" from="s.whatsapp.net" id="{{id}}">
        <picture id="{{another_id}}"/>                
    </iq>
    '''
    def __init__(self, pictureId , _id = None) -> None:
        super().__init__(_id = _id, type = "result")
        self.pictureId = pictureId

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = PictureIqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = ResultSetPictureIqProtocolEntity
        pictureNode = node.getChild("picture")
        entity.pictureId = pictureNode.getAttributeValue("id")
        return entity