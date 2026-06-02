from typing import Any, Optional, Dict, List, Tuple, Union, Callable
class SenderKeyName:
    def __init__(self, groupId, senderAxolotlAddress):
        self.groupId = groupId
        self.sender = senderAxolotlAddress

    def getGroupId(self) -> Any:
        return self.groupId

    def getSender(self):
        return self.sender

    def serialize(self) -> Any:
        return f"{self.groupId}::{self.sender.getName()}::{self.sender.getDeviceId()}"

    def __eq__(self, other):
        if other is None: return False
        if other.__class__ != SenderKeyName: return False

        return self.groupId == other.getGroupId() and self.sender == other.getSender()

    def __hash__(self) -> Any:
        return hash(self.groupId) ^ hash(self.sender)
