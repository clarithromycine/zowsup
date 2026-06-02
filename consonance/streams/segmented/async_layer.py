import asyncio
from typing import Callable, Awaitable

from .async_segmented import AsyncSegmentedStream


class AsyncLayerSegmentedStream(AsyncSegmentedStream):
    """AsyncSegmentedStream adapter that routes I/O through a layer pipeline.

    write_segment(data)  → await write_callback(data)  (i.e. layer.toLower)
    read_segment()       → await asyncio.Queue.get()    (fed by layer.receive)
    """

    def __init__(self, write_callback: Callable[[bytes], Awaitable[None]]) -> None:
        self._write_callback = write_callback
        self._read_queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def read_segment(self) -> bytes:
        return await self._read_queue.get()

    async def write_segment(self, data: bytes) -> None:
        await self._write_callback(data)

    def feed_segment(self, data: bytes) -> None:
        """Feed incoming data (called by the layer's receive method)."""
        self._read_queue.put_nowait(data)
