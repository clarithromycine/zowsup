from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import abc


class SessionStore:
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def loadSession(self, recipientId, recipientType,deviceId):
        pass

    @abc.abstractmethod
    def getSubDeviceSessions(self, recepientId) -> Any:
        pass

    @abc.abstractmethod
    def storeSession(self, recepientId, recipientType,deviceId, sessionRecord):
        pass

    @abc.abstractmethod
    def containsSession(self, recepientId, recipientType, deviceId) -> Any:
        pass

    @abc.abstractmethod
    def deleteSession(self, recepientId,recipientType, deviceId):
        pass

    @abc.abstractmethod
    def deleteAllSessions(self, recepientId) -> Any:
        pass
