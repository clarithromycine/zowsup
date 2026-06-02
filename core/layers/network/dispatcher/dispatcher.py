from typing import Any
class ConnectionCallbacks:
    def onConnected(self) -> Any:
        pass

    def onDisconnected(self) -> Any:
        pass

    def onRecvData(self, data) -> Any:
        pass

    def onConnecting(self) -> Any:
        pass

    def onConnectionError(self, error) -> Any:
        pass


class YowConnectionDispatcher:
    def __init__(self, connectionCallbacks) -> None:
        assert isinstance(connectionCallbacks, ConnectionCallbacks)
        self.connectionCallbacks = connectionCallbacks

    def connect(self, host) -> Any:
        pass

    def disconnect(self) -> Any:
        pass

    def sendData(self, data) -> Any:
        pass