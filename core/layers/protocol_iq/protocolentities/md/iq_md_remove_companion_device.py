from .....structs import  ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
from .....common import YowConstants
from proto import wa_struct_pb2
import time

class MultiDeviceRemoveCompanionDeviceIqProtocolEntity(IqProtocolEntity):

    '''

    remove all

    <iq to='s.whatsapp.net' id='09' xmlns='md' type='set'>
        <remove-companion-device all="true" reason="user_initiated">        
    </iq>


    remove specific jid device
    <iq to='s.whatsapp.net' id='09' xmlns='md' type='set'>
        <remove-companion-device jid="185025005.0:1@s.whatsappnet" reason="user_initiated">        
    </iq>


    '''

    def __init__(self,jid=None,_id=None) -> None:
        super().__init__(_id = _id, _type = "set",to=YowConstants.DOMAIN, xmlns="md")
        self.jid = jid
        self.all = all

    def toProtocolTreeNode(self) -> Any:

        node = super().toProtocolTreeNode()

        attrs = {
            "all":"true",
            "reason":"user_initiated"
        }
        
        if self.jid is not None:
            attrs = {
                "jid":self.jid,
                "reason":"user_initiated"                
            }
            
        removeNode = ProtocolTreeNode("remove-companion-device",attrs)        

        node.addChild(removeNode)        

        return node

        


