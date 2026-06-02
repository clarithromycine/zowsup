from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging

logger = logging.getLogger(__file__)


class ArbitraryStream:
    def read(self, readsize):
        """
        :param readsize -> Any:
        :type readsize: int
        :return:
        :rtype: bytes
        """

    def write(self, data):
        """
        :param data -> Any:
        :type data: bytes
        :return:
        :rtype:
        """
