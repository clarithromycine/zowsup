from ...layers import YowLayer
from typing import Optional, Any, List, Dict, Union

import logging
import struct


logger = logging.getLogger(__name__)


class YowNoiseSegmentsLayer(YowLayer):

    PROP_ENABLED = "org.openwhatsapp.zowsup.prop.noise.segmented_enabled"

    def __init__(self) -> None:
        super().__init__()
        self._read_buffer = bytearray()

    def __str__(self):
        return "Noise Segments Layer"

    async def send(self, data) -> Any:
        if len(data) >= 16777216:
            raise ValueError("data too large to write; length=%d" % len(data))

        if self.getProp(self.PROP_ENABLED, False):
            await self.toLower(struct.pack('>I', len(data))[1:])

        await self.toLower(data)

    async def receive(self, data) -> Any:
        if self.getProp(self.PROP_ENABLED, False):            
            self._read_buffer.extend(data)           
            while len(self._read_buffer) > 3:
                read_size = struct.unpack('>I', b"\x00" + self._read_buffer[:3])[0] # type: int                                                
                if len(self._read_buffer) >= (3 + read_size):
                    data = self._read_buffer[3:read_size+3]
                    self._read_buffer = self._read_buffer[3 + read_size:]
                    await self.toUpper(bytes(data))
                else:
                    break
        else:            
            await self.toUpper(data)
