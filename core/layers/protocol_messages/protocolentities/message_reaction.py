from .protomessage import ProtomessageProtocolEntity
from typing import Optional, Any, List, Dict, Union
from .message import MessageMetaAttributes
from .attributes.attributes_message import MessageAttributes
from proto.e2e_pb2 import *


class ReactionMessageProtocolEntity(ProtomessageProtocolEntity):
    def __init__(self,reaction_attr,message_meta_attributes=None, to=None) -> None:
        
        assert(bool(message_meta_attributes) ^ bool(to)), "Either set message_meta_attributes, or to, and not both"        
        if to:
            message_meta_attributes = MessageMetaAttributes(recipient=to)

        super().__init__("reaction", MessageAttributes(reaction = reaction_attr), message_meta_attributes)




    
