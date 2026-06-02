
import io
import struct
from typing import Any, Optional


class WAByteArrayOutputStream(io.BytesIO):

    
    def __init__(self):

        super().__init__()
        self.byte_order = 'little'  # Little-endian
    
    def get_byte_buffer(self) -> Any:

        data = self.getvalue()
        return {
            'data': data,
            'order': 'little',
            'position': 0,
            'size': len(data)
        }
    
    def get_bytes(self) -> bytes:

        return self.getvalue()
    
    def write_byte(self, value: int) -> None:

        self.write(bytes([value & 0xFF]))
    
    def size(self) -> int:

        return len(self.getvalue())
