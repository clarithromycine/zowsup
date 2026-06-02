from proto import protocol_pb2
from typing import Optional, Any, List, Dict, Union
import json

class SyncActionTimeFormatActionAttribute:
    def __init__(self, isTwentyFourHourFormatEnabled) -> None:
        self.isTwentyFourHourFormatEnabled = isTwentyFourHourFormatEnabled
    
    def encode(self) -> Any:
        pb_obj = protocol_pb2.SyncActionValue.TimeFormatAction()        
        if self.isTwentyFourHourFormatEnabled is not None:
            pb_obj.isTwentyFourHourFormatEnabled = self.isTwentyFourHourFormatEnabled        
        return pb_obj
    
    def indexName(self) -> Any:
        return "time_format"                
    
    def actionVersion(self) -> Any:
        return 7
    
    @staticmethod
    def decodeFrom(self,pb_obj) -> Any:
        isTwentyFourHourFormatEnabled = pb_obj.isTwentyFourHourFormatEnabled if pb_obj.HasField("isTwentyFourHourFormatEnabled") else None

        return SyncActionTimeFormatActionAttribute(
            isTwentyFourHourFormatEnabled=isTwentyFourHourFormatEnabled
        )
