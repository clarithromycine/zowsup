from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import abc


class ECPublicKey:
    __metaclass__ = abc.ABCMeta

    KEY_SIZE = 33

    @abc.abstractmethod
    def serialize(self):
        pass

    @abc.abstractmethod
    def getType(self) -> Any:
        pass


class ECPrivateKey:
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def serialize(self):
        pass

    @abc.abstractmethod
    def getType(self) -> Any:
        pass
