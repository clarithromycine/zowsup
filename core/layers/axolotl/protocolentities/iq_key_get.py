from ....common import YowConstants
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_iq.protocolentities import IqProtocolEntity
from ....structs import ProtocolTreeNode


class GetKeysIqProtocolEntity(IqProtocolEntity):
    def __init__(self, jids, reason=None,_id=None) -> None:
        super().__init__("encrypt", _type="get", to=YowConstants.WHATSAPP_SERVER,_id=_id)
        self.jids = jids
        self.reason = reason

    @property
    def reason(self) -> Any:
        # type: () -> str
        return self._reason

    @reason.setter
    def reason(self, value: Any) -> None:
        # type: (str) -> None
        self._reason = value

    @property
    def jids(self) -> Any:
        # type: () -> list[str]
        return self._jids

    @jids.setter
    def jids(self, value: Any) -> None:
        # type: (list[str]) -> None
        assert type(value) is list, "expected list of jids, got %s" % type(value)
        self._jids = value

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        keyNode = ProtocolTreeNode("key")

        for jid in self.jids:
            attrs = { "jid": jid }
            if self.reason is not None:
                attrs["reason"] = self.reason
            userNode = ProtocolTreeNode("user", attrs)
            keyNode.addChild(userNode)
        node.addChild(keyNode)
        return node
