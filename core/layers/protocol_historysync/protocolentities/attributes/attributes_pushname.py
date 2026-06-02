from proto import e2e_pb2
from typing import Optional, Any, List, Dict, Union

class PushnameAttribute:

    def __init__(self,id=None,pushname=None) -> None:
        self.id = id                
        self.pushname = pushname

    def encode(self) -> Any:
        pb_obj  = e2e_pb2.Pushname()
        pb_obj.id = self.id
        pb_obj.pushname = self.pushname
        return pb_obj
    
    @staticmethod
    def decodeFrom(pb_obj):     
        id = pb_obj.id if pb_obj.HasField("id") else None
        pushname =  pb_obj.pushname if pb_obj.HasField("pushname") else None

        return PushnameAttribute(
            id = id,
            pushname = pushname
        )









        

    
        
