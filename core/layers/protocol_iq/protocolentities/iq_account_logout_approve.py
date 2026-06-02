from .iq import IqProtocolEntity
from typing import Optional, Any, List, Dict, Union
from ....structs import ProtocolTreeNode


class AccountLogoutApproveIqProtocolEntity(IqProtocolEntity):
    
    def __init__(self,refId,approve=True) -> None:
        super().__init__("w:account_defence", _type="set",to="s.whatsapp.net",smax_id="87")
        self.refId = refId
        self.approve = approve

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        logoutNode = ProtocolTreeNode("device_logout", {"approve":"true" if self.approve else "false","id":self.refId})
        node.addChild(logoutNode)
        return node