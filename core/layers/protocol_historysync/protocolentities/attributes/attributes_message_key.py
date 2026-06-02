from proto import e2e_pb2
from typing import Optional, Any, List, Dict, Union
from proto import protocol_pb2

class MessageKeyAttribute:

    def __init__(self,remoteJid=None,fromMe=None,id=None,participant=None) -> None:
        self.remoteJid = remoteJid      
        self.fromMe = fromMe
        self.id = id
        self.participant = participant        

    def encode(self) -> Any:
        pb_obj  = protocol_pb2.MessageKey()

        if self.remoteJid is not None:
            pb_obj.remote_jid = self.remoteJid

        if self.fromMe is not None:
            pb_obj.from_me = self.fromMe

        if self.id is not None:
            pb_obj.id = self.id

        if self.participant is not None:
            pb_obj.participant = self.participant

        return pb_obj
    
    @staticmethod
    def decodeFrom(pb_obj):     

        remoteJid = pb_obj.remote_jid if pb_obj.HasField("remote_jid") else None
        fromMe = pb_obj.fromMe if pb_obj.HasField("fromMe") else None
        id = pb_obj.id if pb_obj.HasField("id") else None
        participant = pb_obj.participant if pb_obj.HasField("participant") else None
        return MessageKeyAttribute(
            remoteJid=remoteJid,
            fromMe=fromMe,
            id=id,
            participant=participant
        )









        

    
        
