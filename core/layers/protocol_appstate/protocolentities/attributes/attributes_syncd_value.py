from proto import protocol_pb2
from typing import Optional, Any, List, Dict, Union

from .....layers.protocol_appstate.protocolentities.attributes import *

class SyncdValueAttribute:
    def __init__(self, blob) -> None:
        self.blob = blob
    
    def encode(self) -> Any:
        pb_obj = protocol_pb2.SyncdValue()

        if self.blob is not None:
            pb_obj.blob = self.blob        

        return pb_obj
    
    @staticmethod
    def decodeFrom(pb_obj):
        blob = pb_obj.blob if pb_obj.HasField("blob") else None
        return SyncdValueAttribute(
            blob=blob
        )