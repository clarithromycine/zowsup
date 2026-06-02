from typing import Any
class Group:
    def __init__(self, groupId, creatorJid, subject, subjectOwnerJid, subjectTime, creationTime, participants=None) -> None:
        self._groupId           = groupId
        self._creatorJid        = creatorJid
        self._subject           = subject
        self._subjectOwnerJid   = subjectOwnerJid
        self._subjectTime       = int(subjectTime)
        self._creationTime      = int(creationTime)
        self._participants      = participants or {}

    def getId(self) -> Any:
        return self._groupId

    def getCreator(self) -> Any:
        return self._creatorJid

    def getOwner(self) -> Any:
        return self.getCreator()

    def getSubject(self) -> Any:
        return self._subject

    def getSubjectOwner(self) -> Any:
        return self._subjectOwnerJid

    def getSubjectTime(self) -> Any:
        return self._subjectTime

    def getCreationTime(self) -> Any:
        return self._creationTime

    def __str__(self):
        return "ID: %s, Subject: %s, Creation: %s, Creator: %s, Subject Owner: %s, Subject Time: %s\nParticipants: %s" %\
                (self.getId(), self.getSubject(), self.getCreationTime(), self.getCreator(),  self.getSubjectOwner(), self.getSubjectTime(), ", ".join(self._participants.keys()))

    def getParticipants(self) -> Any:
        return self._participants
