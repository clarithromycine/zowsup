from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import abc


class IdentityKeyStore:
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def getIdentityKeyPair(self):
        pass

    @abc.abstractmethod
    def getLocalRegistrationId(self) -> Any:
        pass

    @abc.abstractmethod
    def saveIdentity(self, recipientId, recipientType,deviceid, identityKey):
        pass

    @abc.abstractmethod
    def isTrustedIdentity(self, recipientId, recipientType,deviceid,identityKey) -> Any:
        pass
