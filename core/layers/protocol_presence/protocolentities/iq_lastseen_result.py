from ....layers.protocol_iq.protocolentities.iq_result import ResultIqProtocolEntity
from typing import Optional, Any, List, Dict, Union
from ....structs.protocoltreenode import ProtocolTreeNode
class ResultLastseenIqProtocolEntity(ResultIqProtocolEntity):
    def __init__(self, jid, seconds, _id = None) -> None:
        super().__init__(_from=jid, _id=_id)
        self.setSeconds(seconds)

    def setSeconds(self, seconds) -> Any:
        self.seconds = int(seconds)

    def getSeconds(self) -> Any:
        return self.seconds

    def __str__(self):
        out = super(ResultIqProtocolEntity, self).__str__()
        out += "Seconds: %s\n" % self.seconds
        return out

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        node.addChild(ProtocolTreeNode("query", {"seconds": str(self.seconds)}))
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        return ResultLastseenIqProtocolEntity(node["from"], node.getChild("query")["seconds"], node["id"])