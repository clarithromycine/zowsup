from ..iq import IqProtocolEntity
from typing import Optional, Any, List, Dict, Union
from .....structs import ProtocolTreeNode
import codecs
class AccountInfoIqProtocolEntity(IqProtocolEntity):
    
    def __init__(self) -> None:
        super().__init__("urn:xmpp:whatsapp:account", _type="get",to="s.whatsapp.net")

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        accountNode = ProtocolTreeNode("account", {})
        node.addChild(accountNode)
        return node
    
class AccountInfoResultIqProtocolEntity(IqProtocolEntity):
    
    def __init__(self,id,creation,lastReg) -> None:
        super().__init__(_id=id, _type="result",_from="s.whatsapp.net")
        self.creation = creation
        self.lastReg = lastReg

    def setInfo(self,creation,lastReg) -> Any:
        self.creation = creation
        self.lastReg = lastReg
    
    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = AccountInfoResultIqProtocolEntity
        accountNode = node.getChild("account")

        if accountNode:
            creation = int(accountNode.getAttributeValue("creation"))
            last_reg = int(accountNode.getAttributeValue("last_reg"))
            entity.setInfo(creation,last_reg)
            return entity

        return None