import asyncio
import struct
from typing import Optional
import logging

from .async_segmented import AsyncSegmentedStream
from conf.network_config import SEGMENT_READ_TIMEOUT, SEGMENT_WRITE_TIMEOUT

logger = logging.getLogger(__name__)


class AsyncWASegmentedStream(AsyncSegmentedStream):
    """Async WASegmentedStream backed by asyncio.StreamReader/StreamWriter."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._reader = reader
        self._writer = writer

    async def read_segment(self) -> bytes:
        try:
            header = await asyncio.wait_for(
                self._reader.readexactly(3),
                timeout=SEGMENT_READ_TIMEOUT
            )
            size = struct.unpack('>I', b"\x00" + header)[0]
            data = await asyncio.wait_for(
                self._reader.readexactly(size),
                timeout=SEGMENT_READ_TIMEOUT
            )
            return data
        except asyncio.TimeoutError:
            logger.error("Segment read timeout after %ds", SEGMENT_READ_TIMEOUT)
            raise
        except asyncio.IncompleteReadError as e:
            logger.error("Incomplete read: expected %d bytes, got %d", e.expected, len(e.partial))
            raise

    async def write_segment(self, data: bytes) -> None:
        if len(data) >= 16777216:
            raise ValueError(f"data too large to write; length={len(data)}")
        try:
            self._writer.write(struct.pack('>I', len(data))[1:])
            self._writer.write(data)
            await asyncio.wait_for(
                self._writer.drain(),
                timeout=SEGMENT_WRITE_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error("Segment write timeout after %ds", SEGMENT_WRITE_TIMEOUT)
            raise
