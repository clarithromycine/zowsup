from typing import Any, Optional, Dict, List, Tuple, Union, Callable
class PublicKey:
    def __init__(self, data):
        """
        :param data -> Any:
        :type data: bytes
        """
        self._data = data  # type: bytes

    @property
    def data(self):
        return self._data

    def __eq__(self, other) -> Any:
        return type(other) is PublicKey and self.data == other.data
