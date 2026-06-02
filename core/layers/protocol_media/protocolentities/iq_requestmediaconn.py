from ....common import YowConstants
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_iq.protocolentities import IqProtocolEntity
from ....structs import ProtocolTreeNode

class RequestMediaConnIqProtocolEntity(IqProtocolEntity):
    '''
    <iq to="s.whatsapp.net" type="set" xmlns="w:m">
        <media_conn />
    </iq>
    '''

    MEDIA_TYPE_IMAGE = "image"
    MEDIA_TYPE_VIDEO = "video"
    MEDIA_TYPE_AUDIO = "audio"
    MEDIA_TYPE_DOCUMENT = "document"
    MEDIA_TYPE_HISTORY_SYNC = "history-sync"
    XMLNS = "w:m"

    TYPES_MEDIA = (MEDIA_TYPE_AUDIO, MEDIA_TYPE_IMAGE, MEDIA_TYPE_VIDEO, MEDIA_TYPE_DOCUMENT,MEDIA_TYPE_HISTORY_SYNC)

    def __init__(self,  ) -> None:
        super().__init__("w:m", _type = "set", to = YowConstants.WHATSAPP_SERVER)
        

    def __str__(self):
        out = super().__str__()
        return out

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        attribs = {}
        mediaConnNode = ProtocolTreeNode("media_conn", attribs)
        node.addChild(mediaConnNode)
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        assert node.getAttributeValue("type") == "set", "Expected set as iq type in request upload, got %s" % node.getAttributeValue("type")
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = RequestMediaConnIqProtocolEntity
        mediaConnNode = node.getChild("media_conn")        
        return entity
