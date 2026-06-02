from proto import protocol_pb2
from typing import Optional, Any, List, Dict, Union

from .....layers.protocol_appstate.protocolentities.attributes import *

class SyncdKeyIdAttribute:
    def __init__(self, id) -> None:
        self.id = id
    
    def encode(self) -> Any:
        pb_obj = protocol_pb2.KeyId()

        if self.id is not None:
            pb_obj.id = self.id        

        return pb_obj
    
    @staticmethod
    def decodeFrom(pb_obj):
        id = pb_obj.id if pb_obj.HasField("id") else None

        return SyncdKeyIdAttribute(
            id=id
        )