from typing import Any, Optional, Dict, List, Tuple

class Config:
    def __init__(self, version) -> None:
        self._version = version

    def __contains__(self, item) -> Any:
        return self[item] is not None

    def __getitem__(self, item) -> Any:
        return getattr(self, "_%s" % item)

    def __setitem__(self, key, value) -> Any:
        setattr(self, key, value)

    def keys(self) -> Any:
        return [var[1:] for var in vars(self)]

    @property
    def version(self) -> Any:
        return self._version
