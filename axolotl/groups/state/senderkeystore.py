from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import abc


class SenderKeyStore:
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def storeSenderKey(self, senderKeyId, senderKeyRecord):
        """
        :type senderKeyId: str
        :type senderKeyRecord: SenderKeyRecord
        """

    @abc.abstractmethod
    def loadSenderKey(self, senderKeyId) -> Any:
        """
        :type senderKeyId: str
        """
