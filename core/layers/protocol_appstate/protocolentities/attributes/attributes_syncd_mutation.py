from proto import protocol_pb2
from typing import Optional, Any, List, Dict, Union

from .....layers.protocol_appstate.protocolentities.attributes import *

class SyncdMutationAttribute:

    OPERATION_SET = 0
    OPERATION_REMOVE = 1

    def __init__(self, operation,record) -> None:
        self.operation = operation
        self.record = record

    def encode(self) -> Any:
        pb_obj = protocol_pb2.SyncdMutation()

        if self.operation is not None:
            pb_obj.operation = self.operation

        if self.record is not None:
            pb_obj.record.MergeFrom(self.record.encode())

        return pb_obj
    
    @staticmethod
    def decodeFrom(pb_obj):
        operation = pb_obj.operation if pb_obj.HasField("operation") else None

        record = SyncdRecordAttribute.decodeFrom(pb_obj.record) if pb_obj.HasField("record") else None

        return SyncdMutationAttribute(
            operation=operation,
            record=record
        )
    
