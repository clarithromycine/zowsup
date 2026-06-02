from typing import Any
class AppStateSyncKeyDataAttribute:
    def __init__(self, key_data,fingerprint,timestamp) -> None:
        self._key_data = key_data
        self._fingerprint = fingerprint
        self._timestamp=timestamp

    @property
    def key_data(self) -> Any:
        return self._key_data

    @key_data.setter
    def key_data(self, value: Any) -> None:
        self._key_data = value       


    @property
    def fingerprint(self) -> Any:
        return self._fingerprint

    @fingerprint.setter
    def fingerprint(self, value: Any) -> None:
        self._fingerprint = value    
        

    @property
    def timestamp(self) -> Any:
        return self._timestamp

    @timestamp.setter
    def timestamp(self, value: Any) -> None:
        self._timestamp = value            



