from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
class FailureProtocolEntity(ProtocolEntity):

    def __init__(self, reason, violation_reason=None, violation_type=None) -> None:
        super().__init__("failure")
        self.reason = reason
        self.violation_reason = violation_reason
        self.violation_type = violation_type

    def __str__(self):
        out  = "Failure:\n"
        out += "Reason: %s\n" % self.reason
        if self.violation_reason is not None:
            out += "ReasonDetail: %s\n" % self.violation_reason
        if self.violation_type is not None:
            out += "ViolationType: %s\n" % self.violation_type
            
        return out

    def getReason(self) -> Any:
        return self.reason

    def toProtocolTreeNode(self) -> Any:
        return self._createProtocolTreeNode({"reason": self.reason})

    @staticmethod
    def fromProtocolTreeNode(node):
                
        return FailureProtocolEntity( node["reason"],node["violation_reason"],node["vt"] )
