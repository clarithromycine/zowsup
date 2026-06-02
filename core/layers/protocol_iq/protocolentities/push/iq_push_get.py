from ..iq import IqProtocolEntity
from typing import Optional, Any, List, Dict, Union
from .....structs import ProtocolTreeNode
class PushGetIqProtocolEntity(IqProtocolEntity):
    def __init__(self) -> None:
        super().__init__("urn:xmpp:whatsapp:push", _type="get",to="s.whatsapp.net")

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        node.addChild(ProtocolTreeNode("config",{"version":"1"}))
        return node