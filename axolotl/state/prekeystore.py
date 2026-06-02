from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import abc


class PreKeyStore:
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def loadPreKey(self, preKeyId):
        pass

    @abc.abstractmethod
    def storePreKey(self, preKeyId, preKeyRecord) -> Any:
        pass

    @abc.abstractmethod
    def containsPreKey(self, preKeyId):
        pass

    @abc.abstractmethod
    def removePreKey(self, preKeyId) -> Any:
        pass
