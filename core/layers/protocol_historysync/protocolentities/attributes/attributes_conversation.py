from proto import e2e_pb2
from typing import Optional, Any, List, Dict, Union

class ConversationAttribute:

    def __init__(self,id) -> None:
        self.id = id                

    def encode(self) -> Any:
        pb_obj  = e2e_pb2.Conversation()

        if self.id is not None:
            pb_obj.id = self.id

        return pb_obj
    
    @staticmethod
    def decodeFrom(pb_obj):

        id = pb_obj.id if pb_obj.HasField("id") else None
        
        return ConversationAttribute(
            id=id
        ) 
        








        

    
        
