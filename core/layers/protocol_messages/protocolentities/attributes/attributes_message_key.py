from typing import Any
class MessageKeyAttributes:
    def __init__(self, remote_jid, from_me, id, participant=None) -> None:
        self._remote_jid = remote_jid
        self._from_me = from_me
        self._id = id
        self._participant = participant

    def __str__(self):
        attrs = []
        if self.remote_jid is not None:
            attrs.append(("remote_jid", self.remote_jid))
        if self.from_me is not None:
            attrs.append(("from_me", self.from_me))
        if self.id is not None:
            attrs.append(("id", self.id))
        if self.participant is not None:
            attrs.append(("participant", self.participant))

        return "[%s]" % " ".join(map(lambda item: "%s=%s" % item, attrs))

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
    def id(self) -> Any:
        return self._id

    @id.setter
    def id(self, value: Any) -> None:
        self._id = value

    @property
    def participant(self) -> Any:
        return self._participant

    @participant.setter
    def participant(self, value: Any) -> None:
        self._participant = value
