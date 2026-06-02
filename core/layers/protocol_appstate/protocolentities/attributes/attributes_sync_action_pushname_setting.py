from proto import protocol_pb2
from typing import Optional, Any, List, Dict, Union
import json
class SyncActionPushnameSettingAttribute:
    def __init__(self, name) -> None:
        self.name = name

    def encode(self) -> Any:
        pb_obj = protocol_pb2.SyncActionValue.PushNameSetting()        
        if self.name is not None:
            pb_obj.name = self.name
        
        return pb_obj
    

    def indexName(self) -> Any:
        return "setting_pushName"
    
    def actionVersion(self) -> Any:
        return 7    
    
    @staticmethod
    def decodeFrom(self,pb_obj) -> Any:
        name = pb_obj.name if pb_obj.HasField("name") else None

        return SyncActionPushnameSettingAttribute(name=name)
    



