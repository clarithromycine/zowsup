from proto import protocol_pb2
from typing import Optional, Any, List, Dict, Union

class SyncActionNuxActionAttribute:
    def __init__(self, acknowledged) -> None:
        self.acknowledged = acknowledged

    def encode(self) -> Any:
        pb_obj = protocol_pb2.SyncActionValue.NuxAction()        
        if self.acknowledged is not None:
            pb_obj.acknowledged = self.acknowledged
        
        return pb_obj

    
    def indexName(self) -> Any:
        return "nux"                
    
    def actionVersion(self) -> Any:
        return 7
    
    @staticmethod
    def decodeFrom(self,pb_obj) -> Any:
        acknowledged = pb_obj.acknowledged if pb_obj.HasField("acknowledged") else None

        return SyncActionNuxActionAttribute(acknowledged=acknowledged)
