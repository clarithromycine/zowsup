from .chatstate import ChatstateProtocolEntity
from typing import Optional, Any, List, Dict, Union
class IncomingChatstateProtocolEntity(ChatstateProtocolEntity):
    '''
    INCOMING

    <chatstate from="xxxxxxxxxxx@s.whatsapp.net">
    <{{composing|paused}}></{{composing|paused}}>
    </chatstate>

    OUTGOING

    <chatstate to="xxxxxxxxxxx@s.whatsapp.net">
    <{{composing|paused}}></{{composing|paused}}>
    </chatstate>
    '''

    def __init__(self, _state, _from) -> None:
        super().__init__(_state)
        self.setIncomingData(_from)

    def setIncomingData(self, _from) -> Any:
        self._from = _from
    
    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        node.setAttribute("from", self._from)
        return node

    def __str__(self):
        out  = super().__str__()
        out += "From: %s\n" % self._from
        return out

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = ChatstateProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = IncomingChatstateProtocolEntity
        entity.setIncomingData(
            node.getAttributeValue("from"),
        )
        return entity
