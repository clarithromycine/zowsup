from typing import Any, Optional, Dict, List, Tuple, Union, Callable
from dissononce.processing.cipherstate import CipherState

from .streams.segmented.async_segmented import AsyncSegmentedStream


class WANoiseTransportAsync:
    """Async version of WANoiseTransport — encrypt/decrypt + async stream I/O."""

    def __init__(self, stream: AsyncSegmentedStream,
                 send_cipherstate: CipherState,
                 recv_cipherstate: CipherState) -> None:
        self._stream = stream
        self._send_cipherstate = send_cipherstate
        self._recv_cipherstate = recv_cipherstate

    async def send(self, plaintext: bytes) -> None:
        ciphertext = self._send_cipherstate.encrypt_with_ad(b'', plaintext)
        await self._stream.write_segment(ciphertext)

    async def recv(self) -> bytearray:
        ciphertext = await self._stream.read_segment()
        plaintext = self._recv_cipherstate.decrypt_with_ad(b'', ciphertext)
        return bytearray(plaintext)
