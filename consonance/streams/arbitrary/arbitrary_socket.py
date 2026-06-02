from typing import Any, Optional, Dict, List, Tuple, Union, Callable
from socket import socket
import logging

from .arbitrary import ArbitraryStream

logger = logging.getLogger(__name__)


class SocketArbitraryStream(ArbitraryStream):
    def __init__(self, socket):
        """
        :param socket -> Any:
        :type socket: socket
        """
        self._socket = socket # type: socket

    def read(self, readsize):
        return self._socket.recv(readsize)

    def write(self, data) -> Any:
        logger.debug("SocketArbitraryStream write %d bytes", len(data))
        self._socket.send(data)
