from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .ib import IbProtocolEntity
import base64

class NoticeIbProtocolEntity(IbProtocolEntity):
    '''
    <ib from="s.whatsapp.net">
    <notice id="20601218" stage="1" t="1751231052" version="10" type="2" />
    <notice id="20601227" stage="0" t="1756430957" version="4" type="2" />
    <notice id="20601228" stage="0" t="1756430957" version="4" type="2" />
    <notice id="20900727" stage="1" t="1751231053" version="3" type="2" />
    <notice id="20240415" stage="0" t="1756430957" version="1" type="2" />
    <notice id="20250331" stage="0" t="1756430957" version="1" type="1" />
    </ib>
    '''
    def __init__(self, notices) -> None:
        super().__init__()
        self.notices = notices
            

    def __str__(self):
        out = super().__str__()
        out += "ib-notices: %s\n" % base64.b64encode(self.jwsdata)
        return out
    

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IbProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = NoticeIbProtocolEntity
        entity.setProps(node.getChild("offline")["count"])
        return entity    
