from proto import protocol_pb2
from typing import Optional, Any, List, Dict, Union

from .....layers.protocol_appstate.protocolentities.attributes import *

class SyncdExitCodeAttribute:
    def __init__(self, code,text) -> None:
        self.code = code
        self.text = text
    
    def encode(self) -> Any:
        pb_obj = protocol_pb2.SyncdExitCode()
        if self.code is not None:
            pb_obj.code = self.code   

        if self.text is not None:
            pb_obj.text = self.text     

        return pb_obj
    
    @staticmethod
    def decodeFrom(pb_obj):
        code = pb_obj.code if pb_obj.HasField("code") else None

        text = pb_obj.text if pb_obj.HasField("text") else None

        return SyncdExitCodeAttribute(
            code=code,
            text=text
        )