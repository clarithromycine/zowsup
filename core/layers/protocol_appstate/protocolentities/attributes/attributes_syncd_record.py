from proto import protocol_pb2
from typing import Optional, Any, List, Dict, Union

from .....layers.protocol_appstate.protocolentities.attributes import *

class SyncdRecordAttribute:

    def __init__(self, index,value,keyId) -> None:
        self.index = index
        self.value = value
        self.keyId = keyId

    def encode(self) -> Any:
        pb_obj = protocol_pb2.SyncdRecord()

        if self.index is not None:
            pb_obj.index.MergeFrom(self.index.encode())
            
        if self.value is not None:
            pb_obj.value.MergeFrom(self.value.encode()) 

        if self.keyId is not None:
            pb_obj.keyId.MergeFrom(self.keyId.encode())

        return pb_obj

    @staticmethod    
    def decodeFrom(pb_obj):

        index = SyncdIndexAttribute.decodeFrom(pb_obj.index) if pb_obj.HasField("index") else None
        value = SyncdValueAttribute.decodeFrom(pb_obj.value) if pb_obj.HasField("value") else None
        keyId = SyncdKeyIdAttribute.decodeFrom(pb_obj.keyId) if pb_obj.HasField("keyId") else None

        return SyncdRecordAttribute(
            index=index,
            value=value,
            keyId=keyId
        )