from proto import e2e_pb2
from typing import Optional, Any, List, Dict, Union
from proto import protocol_pb2
from .attributes_sync_action_value import SyncActionValueAttribute

class SyncActionDataAttribute:
    def __init__(self, 
                 index,
                 value,
                 padding,
                 version
        ) -> None:
        self.index = index
        self.value= value
        self.padding = padding
        self.version =version


    def encode(self) -> Any:

        pb_obj = protocol_pb2.SyncActionData()

        if self.index is not None:
            pb_obj.index = self.index
        
        if self.value is not None:
            pb_obj.value.MergeFrom(self.value.encode())   #value是一个SyncActionValueAttribute

        if self.padding is not None:
            pb_obj.padding = self.padding

        
        if self.version is not None:
            pb_obj.version = self.version

        return pb_obj

    @staticmethod
    def decodeFrom(pb_obj):
        index = pb_obj.index if pb_obj.HasField("index") else None    
        value = SyncActionValueAttribute.decodeFrom(pb_obj.value) if pb_obj.HasField("value") else None    
        padding = pb_obj.padding if pb_obj.HasField("padding") else None    
        version = pb_obj.version if pb_obj.HasField("version") else None    
        return SyncActionValueAttribute(
            index=index,
            value=value,
            padding=padding,
            version=version            
        )
    
    @staticmethod
    def createFromSyncActionValue(valueObj):
        return SyncActionDataAttribute(
            index = valueObj.getIndexName().encode(),
            value = valueObj,
            padding = bytes(0),
            version = valueObj.getVersion(),
        )    

    



                


