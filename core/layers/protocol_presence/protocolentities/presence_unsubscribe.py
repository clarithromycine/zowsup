from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .presence import PresenceProtocolEntity
class UnsubscribePresenceProtocolEntity(PresenceProtocolEntity):

    '''
    <presence type="unsubscribe" to="jid"></presence>
    '''

    def __init__(self, jid) -> None:
        super().__init__("unsubscribe")
        self.setProps(jid)

    def setProps(self, jid) -> Any:
        self.jid = jid
    
    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        node.setAttribute("to", self.jid)
        return node

    def __str__(self):
        out  = super().__str__()
        out += "To: %s\n" % self.jid
        return out

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = PresenceProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = UnsubscribePresenceProtocolEntity
        entity.setProps(
            node.getAttributeValue("to")
        )
        return entity
