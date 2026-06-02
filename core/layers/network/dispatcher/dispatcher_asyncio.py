"""
Phase 2 — Asyncio-based connection dispatcher.

Replaces asyncore.loop() + select/poll with asyncio.open_connection().
Uses python_socks for async SOCKS5 proxy support.

This dispatcher is designed to be driven by an external asyncio event loop
(created and run by YowStack in a later phase). It does NOT call asyncio.run()
itself.
"""

import asyncio
import logging
from typing import Optional, Tuple

from ....layers.network.dispatcher.dispatcher import (
    ConnectionCallbacks,
    YowConnectionDispatcher,
)
from conf.network_config import CONNECT_TIMEOUT, READ_TIMEOUT, WRITE_TIMEOUT

logger = logging.getLogger(__name__)

# Read size per iteration — matches the 1024 used by the asyncore dispatcher
_DEFAULT_READ_SIZE = 1024


class AsyncioConnectionDispatcher(YowConnectionDispatcher):
    """
    Connection dispatcher backed by asyncio streams.

    Lifecycle:
        connect(host)  → opens TCP (optionally through SOCKS5 proxy),
                         fires onConnected, starts _read_loop task.
        sendData(data) → schedules a write on the writer.
        disconnect()   → cancels read loop, closes writer, fires onDisconnected.

    All public methods are *synchronous* but schedule work on the running
    asyncio event loop via `asyncio.ensure_future` / `loop.call_soon_threadsafe`.
    In Phase 5 the callers will be async themselves, but for now we bridge.
    """

    def __init__(self, connectionCallbacks: ConnectionCallbacks) -> None:
        super().__init__(connectionCallbacks)
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._read_task: Optional[asyncio.Task] = None
        self._connected = False
        self._networkEnv = connectionCallbacks.getStack().getProp("env").networkEnv

    # ------------------------------------------------------------------
    # Public (sync bridge → async)
    # ------------------------------------------------------------------

    def connect(self, host: Tuple[str, int]) -> None:
        """Schedule an async connection.  The running loop is expected
        to already exist (started by YowStack or tests)."""
        logger.debug("connect(%s)", host)
        self.connectionCallbacks.onConnecting()
        asyncio.ensure_future(self._async_connect(host))

    def disconnect(self) -> None:
        """Cancel the read loop and close the transport."""
        logger.debug("disconnect()")
        self._cancel_read_task()
        self._close_writer()
        if self._connected:
            self._connected = False
            asyncio.ensure_future(self.connectionCallbacks.onDisconnected())

    def sendData(self, data: bytes) -> None:
        if not self._connected or self._writer is None:
            logger.warning("Attempted to send %d bytes while not connected", len(data))
            return
        try:
            self._writer.write(data)
            # drain is a coroutine — schedule it without blocking, with timeout
            asyncio.ensure_future(self._safe_drain())
        except Exception:
            logger.exception("Error sending data")
            self.disconnect()
    
    async def _safe_drain(self) -> None:
        """Drain write buffer with timeout."""
        if self._writer is None:
            return
        try:
            await asyncio.wait_for(self._writer.drain(), timeout=WRITE_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("Write drain timeout after %ds", WRITE_TIMEOUT)
            self.disconnect()
        except Exception as exc:
            logger.error("Write drain error: %s", exc)
            self.disconnect()

    # ------------------------------------------------------------------
    # Async internals
    # ------------------------------------------------------------------

    async def _async_connect(self, host: Tuple[str, int]) -> None:
        """Open a TCP connection (with optional SOCKS5 proxy)."""
        try:
            reader, writer = await asyncio.wait_for(
                self._open_connection(host),
                timeout=CONNECT_TIMEOUT
            )
            self._reader = reader
            self._writer = writer
            self._connected = True
            logger.info("Connected to %s:%d", *host)
            await self.connectionCallbacks.onConnected()
            # Start the read loop as a background task
            self._read_task = asyncio.ensure_future(self._read_loop())
        except asyncio.TimeoutError:
            logger.error("Connection timeout to %s:%d after %ds", *host, CONNECT_TIMEOUT)
            self._connected = False
            await self.connectionCallbacks.onConnectionError(
                TimeoutError(f"Connection to {host[0]}:{host[1]} timed out after {CONNECT_TIMEOUT}s")
            )
        except Exception as exc:
            logger.error("Connection failed: %s", exc)
            self._connected = False
            await self.connectionCallbacks.onConnectionError(exc)

    async def _open_connection(
        self, host: Tuple[str, int]
    ) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Return (reader, writer), going through a SOCKS5 proxy if configured."""
        if self._networkEnv.type != "direct":
            return await self._open_proxy_connection(host)
        logger.debug("Direct connection to %s:%d", *host)
        return await asyncio.open_connection(host[0], host[1])

    async def _open_proxy_connection(
        self, host: Tuple[str, int]
    ) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Connect through a SOCKS5 proxy using python-socks."""
        from python_socks.async_.asyncio import Proxy  # lazy import

        env = self._networkEnv
        logger.debug(
            "SOCKS5 proxy %s:%d → %s:%d",
            env.host,
            env.port,
            host[0],
            host[1],
        )
        proxy = Proxy.from_url(
            f"socks5://{env.username}:{env.password}@{env.host}:{env.port}",
            rdns=True,
        )
        sock = await proxy.connect(dest_host=host[0], dest_port=host[1])
        # Wrap the already-connected socket in asyncio streams
        return await asyncio.open_connection(sock=sock)

    async def _read_loop(self) -> None:
        """Continuously read from the stream and deliver to the layer above."""
        assert self._reader is not None
        try:
            while True:
                try:
                    data = await asyncio.wait_for(
                        self._reader.read(_DEFAULT_READ_SIZE),
                        timeout=READ_TIMEOUT
                    )
                    if not data:
                        logger.debug("Remote end closed connection (EOF)")
                        break
                    await self.connectionCallbacks.onRecvData(data)
                except asyncio.TimeoutError:
                    logger.warning("Read timeout after %ds, disconnecting", READ_TIMEOUT)
                    break
        except asyncio.CancelledError:
            logger.debug("Read loop cancelled")
            return
        except Exception as exc:
            logger.error("Read loop error: %s", exc)
        # Connection lost — clean up
        self._connected = False
        self._close_writer()
        await self.connectionCallbacks.onDisconnected()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cancel_read_task(self) -> None:
        if self._read_task is not None and not self._read_task.done():
            self._read_task.cancel()
            self._read_task = None

    def _close_writer(self) -> None:
        if self._writer is not None:
            try:
                self._writer.close()
            except Exception:
                pass
            self._writer = None
            self._reader = None
