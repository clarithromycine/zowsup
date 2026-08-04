from ..iq import IqProtocolEntity
from typing import Optional, Any, List, Dict, Union
from .....structs import ProtocolTreeNode
from .....common import YowConstants
class PushGetIqProtocolEntity(IqProtocolEntity):
    def __init__(self) -> None:
        super().__init__("urn:xmpp:whatsapp:push", _type="get",to="s.whatsapp.net")

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        node.addChild(ProtocolTreeNode("config",{"version":"1"}))
        return node



class PushGetResultIqProtocolEntity(IqProtocolEntity):

    def __init__(self,_id=None,pkey=None,voipPayloadType=None,platform=None,pushId=None) -> None:
        super().__init__(_id = _id, _type = "result",to=YowConstants.DOMAIN)
        self.pkey = None      
        self.voipPayloadType = voipPayloadType
        self.platform = platform
        self.pushId = pushId

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = PushGetResultIqProtocolEntity

        configNode = node.getChild("config")
        if configNode is not None:      
            entity.pkey = configNode.getAttributeValue("pkey")   
            entity.voipPayloadType = configNode.getAttributeValue("voip_payload_type")   
            entity.platform = configNode.getAttributeValue("platform")   
            entity.pushId = configNode.getAttributeValue("id")   
            return entity
        else:
            return None