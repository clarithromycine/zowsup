from ....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_iq.protocolentities import IqProtocolEntity
import time

class SyncIqProtocolEntity(IqProtocolEntity):

    def __init__(self, _type, _id = None, sid = None, index = 0, last = True) -> None:
        super().__init__("usync", _id = _id, _type = _type)
        self.setSyncProps(sid, index, last)

    def setSyncProps(self, sid, index, last) -> Any:
        self.sid = sid if sid else str((int(time.time()) + 11644477200) * 10000000)
        self.index = int(index)
        self.last = last


    def __str__(self):
        out  = super().__str__()
        out += "sid: %s\n" % self.sid
        out += "index: %s\n" % self.index
        out += "last: %s\n" % self.last
        return out

    def toProtocolTreeNode(self) -> Any:

        syncNodeAttrs = {
            "sid":      self.sid,
            "index":    str(self.index),
            "last":     "true" if self.last else "false"
        }

        syncNode = ProtocolTreeNode("usync", syncNodeAttrs)

        node = super().toProtocolTreeNode()
        node.addChild(syncNode)
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        syncNode         = node.getChild("usync")
        entity           = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = SyncIqProtocolEntity


        entity.setSyncProps(
            syncNode.getAttributeValue("sid"),
            syncNode.getAttributeValue("index"),
            syncNode.getAttributeValue("last")
            )


        return entity
