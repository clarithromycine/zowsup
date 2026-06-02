import base64
import hashlib
import struct
from collections import defaultdict
from typing import Any, List, Dict, Tuple

from common.utils import Utils
from .hash_state import HashState


class LTHash:

    EXPAND_SIZE = 128
    SALT = b"WhatsApp Patch Integrity"
    
    def __init__(self, hash_state) -> None:
        self.salt = LTHash.SALT
        self.type = hash_state.type
        self.hash = hash_state.hash
        self.index_value_map = dict(hash_state.indexValueMap)
        self.version = hash_state.version
        self.add = []
        self.subtract = []

    def mix(self, index_mac: bytes, value_mac: bytes, operation: int) -> Any:
        index_mac_base64 = base64.b64encode(index_mac).decode('utf-8')
        prev_op = self.index_value_map.get(index_mac_base64)
        
        if operation == 1:  #REMOVE
            if prev_op is None:
                return
            self.index_value_map.pop(index_mac_base64, None)
        else:   #SET
            self.add.append(value_mac)
            self.index_value_map[index_mac_base64] = value_mac
        
        if prev_op:
            self.subtract.append(prev_op)

    def finish(self) -> HashState:
        subtracted = self._perform(self.hash, False)
        self.hash = self._perform(subtracted, True)
        return HashState(
            type=self.type,
            hash=self.hash,
            indexValueMap=self.index_value_map,
            version = self.version+1
        )
    def _perform(self, input_data: bytes, sum_op: bool) -> bytes:
        items = self.add if sum_op else self.subtract
        for item in items:
            input_data = self._perform_single(input_data, item, sum_op)
        return input_data

    def _perform_single(self, input_data: bytes, buffer: bytes, sum_op: bool) -> bytes:

        expanded = Utils.extract_and_expand(buffer,LTHash.SALT,128)        

        input_values = struct.unpack('<' + 'H' * (len(input_data) // 2), input_data)
        expanded_values = struct.unpack('<' + 'H' * (len(expanded) // 2), expanded)

        output_values = [
            (a + b if sum_op else a - b) & 0xFFFF
            for a, b in zip(input_values, expanded_values)
        ]
        
        return struct.pack('<' + 'H' * len(output_values), *output_values)


