from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import abc

from .identitykeystore import IdentityKeyStore
from .prekeystore import PreKeyStore
from .sessionstore import SessionStore
from .signedprekeystore import SignedPreKeyStore
from .pollstore import PollStore
from .taskmsgstore import TaskMsgStore


class AxolotlStore(IdentityKeyStore, PreKeyStore, SignedPreKeyStore, SessionStore,PollStore,TaskMsgStore):
    __metaclass__ = abc.ABCMeta
