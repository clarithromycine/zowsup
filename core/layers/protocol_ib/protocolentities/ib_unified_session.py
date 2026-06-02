from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .ib import IbProtocolEntity
import base64
import time

class UnifiedSessionIbProtocolEntity(IbProtocolEntity):
    '''
    <ib>
        <unified_session id='346845821' />
    </ib>

    '''
    def __init__(self, id=None) -> None:
        super().__init__()
        if id is None:
            id = str((int(time.time()*1000)+ 259200000) % 604800000)

        self.id = id
                    
    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        sessionNode = ProtocolTreeNode("unified_session",{"id":self.id})
        node.addChild(sessionNode)
        return node

    def __str__(self):
        out = super().__str__()
        out += "ib-unifieid_session: id=%s\n" % base64.b64encode(self.id)
        return out
