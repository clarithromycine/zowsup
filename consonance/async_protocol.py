import logging
from typing import Callable, Optional

from .async_handshake import WAHandshakeAsync
from .async_transport import WANoiseTransportAsync
from .config.client import ClientConfig
from .exceptions.handshake_failed_exception import HandshakeFailedException
from .streams.segmented.async_segmented import AsyncSegmentedStream

logger = logging.getLogger(__name__)


class WANoiseProtocolAsync:
    """Async version of WANoiseProtocol — state machine + async handshake/transport."""

    STATE_INIT = 'init'
    STATE_HANDSHAKE = 'handshake'
    STATE_TRANSPORT = 'transport'
    STATE_ERROR = 'error'

    def __init__(self, version_major: int, version_minor: int,
                 protocol_state_callbacks: Optional[Callable] = None) -> None:
        self._version_major = version_major
        self._version_minor = version_minor
        self._protocol_state_callbacks = protocol_state_callbacks
        self._rs = None
        self._transport: Optional[WANoiseTransportAsync] = None
        self._state = self.STATE_INIT

    def _set_state(self, new_state: str) -> None:
        self._state = new_state
        if self._protocol_state_callbacks is not None:
            self._protocol_state_callbacks(self._state)

    @property
    def state(self) -> str:
        return self._state

    @property
    def rs(self):
        return self._rs

    async def start(self, stream: AsyncSegmentedStream, client_config: ClientConfig,
                    s, rs=None, mode=None,
                    identity=None, regid=None, signedprekey=None, deviceid=None) -> None:
        self._set_state(self.STATE_HANDSHAKE)

        handshake = WAHandshakeAsync(self._version_major, self._version_minor)
        if mode is not None:
            handshake.setmode(mode)
        if identity is not None:
            handshake.setIdentity(identity)
        if regid is not None:
            handshake.setRegistrationId(regid)
        if signedprekey is not None:
            handshake.setSignedPreKey(signedprekey)
        if deviceid is not None:
            handshake.setDeviceId(deviceid)

        try:
            result = await handshake.perform(client_config, stream, s, rs)            
            if result is not None:
                self._rs = handshake.rs
                self._transport = WANoiseTransportAsync(stream, result[0], result[1])
                self._set_state(self.STATE_TRANSPORT)
            else:
                raise HandshakeFailedException("No cipherstates")
        except HandshakeFailedException:
            self._set_state(self.STATE_ERROR)
            self.reset()
            raise

    def reset(self) -> None:
        self._set_state(self.STATE_INIT)
        self._transport = None

    async def send(self, data: bytes) -> None:
        if self._state != self.STATE_TRANSPORT:
            raise RuntimeError(f"Cannot send in state {self._state}")
        try:
            await self._transport.send(data)
        except Exception:
            logger.error("network error", exc_info=True)

    async def receive(self) -> bytearray:
        if self._state != self.STATE_TRANSPORT:
            raise RuntimeError(f"Cannot receive in state {self._state}")
        return await self._transport.recv()
