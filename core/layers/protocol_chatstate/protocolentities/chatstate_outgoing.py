from .chatstate import ChatstateProtocolEntity
from typing import Optional, Any, List, Dict, Union
class OutgoingChatstateProtocolEntity(ChatstateProtocolEntity):
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

    def __init__(self, _state, _to, participant=None) -> None:
        super().__init__(_state)
        self.setOutgoingData(_to,participant)

    def setOutgoingData(self, _to, participant) -> Any:
        self._to = _to
        self.participant = participant
    
    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        node.setAttribute("to", self._to)
        if self.participant:
            node.setAttribute("participant",self.participant)
        return node

    def __str__(self):
        out  = super().__str__()
        out += "To: %s\n" % self._to
        if self.participant:
            out += "Participant: %s\n" % self.participant

        return out

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = ChatstateProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = OutgoingChatstateProtocolEntity
        entity.setOutgoingData(
            node.getAttributeValue("to"),
            node.getAttributeValue("participant")
        )

        return entity
