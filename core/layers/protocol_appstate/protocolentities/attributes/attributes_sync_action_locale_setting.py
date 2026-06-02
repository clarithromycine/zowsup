from proto import protocol_pb2
from typing import Optional, Any, List, Dict, Union
import json
class SyncActionLocaleSettingAttribute:
    def __init__(self, locale) -> None:
        self.locale = locale
    
    def encode(self) -> Any:
        pb_obj = protocol_pb2.SyncActionValue.LocaleSetting()        
        if self.locale is not None:
            pb_obj.locale = self.locale        
        return pb_obj
    
    def indexName(self) -> Any:
        return "setting_locale"                
    
    def actionVersion(self) -> Any:
        return 7
    
    @staticmethod
    def decodeFrom(self,pb_obj) -> Any:
        locale = pb_obj.locale if pb_obj.HasField("locale") else None
        return SyncActionLocaleSettingAttribute(locale=locale)








