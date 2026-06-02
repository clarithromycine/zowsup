from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from typing import Optional, Any, List, Dict, Union
from proto import e2e_pb2

class ReactionAttributes:
    def __init__(self, msgid, remote_jid, from_me,text,sender_timestamp_ms) -> None:

        self._msgid = msgid
        self._remote_jid = remote_jid        
        self._from_me = from_me
        self._text = text
        self._sender_timestamp_ms = sender_timestamp_ms        

    def __str__(self):
        attrs = []        
        if self.msgid is not None:
            attrs.append(("msgid", self.msgid))
        if self.remote_jid is not None:
            attrs.append(("remote_jid",self.remote_jid))
        if self.from_me is not None:
            attrs.append(("from_me",self.from_me))
        if self.text is not None:
            attrs.append(("text",self.text))
        if self.sender_timestamp_ms is not None:
            attrs.append(("sender_timestamp_ms",self.sender_timestamp_ms))
                 
        return "[%s]" % " ".join(map(lambda item: "%s=%s" % item, attrs))

    @property
    def msgid(self) -> Any:
        return self._msgid

    @msgid.setter
    def msgid(self, value: Any) -> None:
        self._msgid = value

    @property
    def remote_jid(self) -> Any:
        return self._remote_jid

    @remote_jid.setter
    def remote_jid(self, value: Any) -> None:
        self._remote_jid = value


    @property
    def from_me(self) -> Any:
        return self._from_me

    @from_me.setter
    def from_me(self, value: Any) -> None:
        self._from_me = value


    @property
    def text(self) -> Any:
        return self._text

    @text.setter
    def text(self, value: Any) -> None:
        self._text = value


    @property
    def sender_timestamp_ms(self) -> Any:
        return self._sender_timestamp_ms

    @sender_timestamp_ms.setter
    def sender_timestamp_ms(self, value: Any) -> None:
        self._sender_timestamp_ms = value


