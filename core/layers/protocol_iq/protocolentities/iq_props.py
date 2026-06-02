from .iq import IqProtocolEntity
from typing import Optional, Any, List, Dict, Union
from ....structs import ProtocolTreeNode
class PropsIqProtocolEntity(IqProtocolEntity):
    def __init__(self) -> None:
        super().__init__("w", _type="get",to="s.whatsapp.net")

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        node.addChild(ProtocolTreeNode("props",{"protocol":"2","hash":""}))
        return node