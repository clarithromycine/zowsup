from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .iq import IqProtocolEntity
import time
import logging

logger = logging.getLogger(__name__)

class CleanDirtyIqProtocolEntity(IqProtocolEntity):

    #type: account_sync | groups

    def __init__(self, _id = None,type = "account_sync") -> None:
        super().__init__("urn:xmpp:whatsapp:dirty" , _id = _id, _type = "set",to="s.whatsapp.net")
        self.type = type

    def toProtocolTreeNode(self) -> Any:        
        node = super().toProtocolTreeNode()
        clean = ProtocolTreeNode("clean",{'type':self.type,"timestamp":str(int(time.time()))})
        node.addChild(clean)     
        logger.debug(node) 
        return node    
