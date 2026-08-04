from typing import Any
class PeerDataOperationRequestResponseMessageAttribute:
    def __init__(self, nonce,waFbid,forceRefresh) -> None:
        self._nonce  = nonce
        self._waFbid = waFbid
        self._forceRefresh = forceRefresh

    @property
    def nonce(self) -> Any:
        return self._nonce

    @nonce.setter
    def nonce(self, value: Any) -> None:
        self._nonce = value       


    @property
    def waFbid(self) -> Any:
        return self._waFbid

    @waFbid.setter
    def waFbid(self, value: Any) -> None:
        self._waFbid = value    
        

    @property
    def forceRefresh(self) -> Any:
        return self._forceRefresh

    @forceRefresh.setter
    def forceRefresh(self, value: Any) -> None:
        self._forceRefresh = value            



