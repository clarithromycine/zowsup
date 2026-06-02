from typing import Any
class AppStateSyncKeyShareAttribute:
    def __init__(self, keys) -> None:
        self._keys = keys

    @property
    def keys(self) -> Any:
        return self._keys

    @keys.setter
    def keys(self, value: Any) -> None:
        self._keys = value


