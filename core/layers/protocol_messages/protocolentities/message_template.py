from .protomessage import ProtomessageProtocolEntity
from typing import Optional, Any, List, Dict, Union
from .message import MessageMetaAttributes
from .attributes.attributes_message import MessageAttributes
from proto.e2e_pb2 import *


'''
BUTTON , LIST AND TEMPLATE MESSAGE WAS DEPRECATED BECAUSE OF THE  SERVER FILTERS  UPDATED AT 2023.5.11
'''

class TemplateMessageProtocolEntity(ProtomessageProtocolEntity):
    def __init__(self,body,message_meta_attributes=None, to=None) -> None:
        # flexible attributes for temp backwards compat
        assert(bool(message_meta_attributes) ^ bool(to)), "Either set message_meta_attributes, or to, and not both"        
        if to:
            message_meta_attributes = MessageMetaAttributes(recipient=to)

        super().__init__("text", MessageAttributes(template = body), message_meta_attributes)
        self.setBody(body)        

    def getBody(self) -> Any:
        #obsolete
        return self._body

    def setBody(self, body) -> Any:
        #obsolete
        self._body = body
