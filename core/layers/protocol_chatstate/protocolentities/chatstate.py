from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
class ChatstateProtocolEntity(ProtocolEntity):

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

    STATE_TYPING = "composing"
    STATE_PAUSED = "paused"
    STATES = (STATE_TYPING, STATE_PAUSED)

    def __init__(self, _state) -> None:
        super().__init__("chatstate")
        assert _state in self.__class__.STATES, f"Expected chat state to be in {self.__class__.STATES}, got {_state}"
        self._state = _state

    def getState(self) -> Any:
        return self._state

    def toProtocolTreeNode(self) -> Any:
        node = self._createProtocolTreeNode({}, None, data = None)
        node.addChild(ProtocolTreeNode(self._state))
        return node

    def __str__(self):
        out  = "CHATSTATE:\n"
        out += "State: %s\n" % self._state
        return out

    @staticmethod
    def fromProtocolTreeNode(node):
        return ChatstateProtocolEntity(
            node.getAllChildren()[0].tag,
            )
