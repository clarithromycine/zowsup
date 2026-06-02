from typing import Any
class AppStateSyncKeyIdAttribute:
    def __init__(self, key_id) -> None:
        self._key_id = key_id


    @property
    def key_id(self) -> Any:
        return self._key_id

    @key_id.setter
    def key_id(self, value: Any) -> None:
        self._keys_id = value


