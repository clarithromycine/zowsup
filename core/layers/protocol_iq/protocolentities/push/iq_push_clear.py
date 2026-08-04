from ..iq import IqProtocolEntity
from typing import Optional, Any, List, Dict, Union
from .....structs import ProtocolTreeNode
class PushClearIqProtocolEntity(IqProtocolEntity):
    def __init__(self,platform) -> None:
        super().__init__("urn:xmpp:whatsapp:push", _type="set",to="s.whatsapp.net")
        self.platform = platform

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        node.addChild(ProtocolTreeNode("clear",{"platform":self.platform}))
        return node