from typing import Any
class AppStateSyncKeyFingerprintAttribute:
    def __init__(self, raw_id,current_index,device_indexes) -> None:
        self._raw_id = raw_id
        self._current_index = current_index
        self._device_indexes=device_indexes

    @property
    def raw_id(self) -> Any:
        return self._raw_id

    @raw_id.setter
    def raw_id(self, value: Any) -> None:
        self._raw_id = value       


    @property
    def current_index(self) -> Any:
        return self._current_index

    @current_index.setter
    def current_index(self, value: Any) -> None:
        self._current_index = value    
        

    @property
    def device_indexes(self) -> Any:
        return self._device_indexes

    @device_indexes.setter
    def device_indexes(self, value: Any) -> None:
        self._device_indexes = value            



