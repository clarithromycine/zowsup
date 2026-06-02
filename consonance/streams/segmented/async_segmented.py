from typing import Any, Optional, Dict, List, Tuple, Union, Callable
from abc import ABC, abstractmethod


class AsyncSegmentedStream(ABC):
    """Abstract base class for async segmented streams."""

    @abstractmethod
    async def read_segment(self) -> bytes:
        ...

    @abstractmethod
    async def write_segment(self, data: bytes) -> None:
        ...
