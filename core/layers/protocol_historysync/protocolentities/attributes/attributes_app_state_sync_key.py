from typing import Any
class AppStateSyncKeyAttribute:
    def __init__(self, key_id,key_data) -> None:
        self._key_id = key_id
        self._key_data = key_data

    @property
    def key_id(self) -> Any:
        return self._key_id

    @key_id.setter
    def key_id(self, value: Any) -> None:
        self._keys_id = value

    @property
    def key_data(self) -> Any:
        return self._key_data

    @key_data.setter
    def key_data(self, value: Any) -> None:
        self._key_data = value        


