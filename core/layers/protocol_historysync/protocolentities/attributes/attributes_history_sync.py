from proto import e2e_pb2
from typing import Optional, Any, List, Dict, Union

from .attributes_conversation import ConversationAttribute
from .attributes_past_participants import PastParticipantsAttribute
from .attributes_web_message_info import WebMessageInfoAttribute
from .attributes_pushname import PushnameAttribute

class HistorySyncAttribute:

    INITIAL_BOOTSTRAP = 0
    INITIAL_STATUS_V3 = 1
    FULL = 2
    RECENT = 3
    PUSH_NAME = 4
    NON_BLOCKING_DATA = 5
    ON_DEMAND = 6

    def __init__(self, syncType, conversations=None, pastParticipants=None,statusV3Messages=None,pushnames=None) -> None:
        self.syncType = syncType
        self.conversations = conversations
        self.pastParticipants = pastParticipants       
        self.statusV3Messages =  statusV3Messages
        self.pushnames = pushnames
    
    def encode(self) -> Any:
        pb_obj  = e2e_pb2.HistorySync()

        if self.syncType is not None:
            pb_obj.syncType = self.syncType
        
        if self.conversations is not None:
            for item in self.conversations:            
                pb_obj.conversations.append(item.encode())

        if self.pastParticipants is not None:
            for item in self.pastParticipants:
                pb_obj.pastParticipants.append(item.encode())

        if self.statusV3Messages is not None:
            for item in self.statusV3Messages:
                pb_obj.statusV3Messages.append(item.encode())

        if self.pushnames is not None:
            for item in self.pushnames:
                pb_obj.pushnames.append(item.encode())

        return pb_obj
    
    @staticmethod
    def decodeFrom(pb_obj):
        
        syncType = pb_obj.syncType if pb_obj.HasField("syncType") else None        
        
        conversations = []
        for item in pb_obj.conversations:
            conversations.append(ConversationAttribute.decodeFrom(item))
    
        pastParticipants = []
        for item in pb_obj.pastParticipants:
            pastParticipants.append(PastParticipantsAttribute.decodeFrom(item))

        statusV3Messages = []

        for item in pb_obj.statusV3Messages:
            statusV3Messages.append(WebMessageInfoAttribute.decodeFrom(item))

        pushnames = []
        for item in pb_obj.pushnames:
            pushnames.append(PushnameAttribute.decodeFrom(item))
        
        return HistorySyncAttribute(
            syncType=syncType,
            conversations=conversations,
            pastParticipants=pastParticipants,
            statusV3Messages=statusV3Messages,
            pushnames=pushnames
        )










        

    
        
