from proto import protocol_pb2
from typing import Optional, Any, List, Dict, Union
import json

class SyncActionPrimaryVersionActionAttribute:
    def __init__(self, version) -> None:
        self.version = version

    def encode(self) -> Any:

        pb_obj  = protocol_pb2.SyncActionValue.PrimaryVersionAction()

        if self.version is not None:
            pb_obj.version = self.version        
        return pb_obj     

    def indexName(self) -> Any:
        return "primary_version"                
    
    def actionVersion(self) -> Any:
        return 7   
    
    @staticmethod
    def decodeFrom(pb_obj):

        version = pb_obj.version if pb_obj.HasField("version") else None
        
        return SyncActionPrimaryVersionActionAttribute(
            version=version
        )