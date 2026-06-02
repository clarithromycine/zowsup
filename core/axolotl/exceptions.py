from typing import Optional, Any

class NoSessionException(Exception):
    pass


class UntrustedIdentityException(Exception):
    def __init__(self, name: Any, identity_key: Any) -> None:
        self._name = name
        self._identity_key = identity_key

    @property
    def name(self) -> Any:
        return self._name

    @property
    def identity_key(self) -> Any:
        return self._identity_key


class InvalidMessageException(Exception):
    pass


class InvalidKeyIdException(Exception):
    pass


class DuplicateMessageException(Exception):
    pass

