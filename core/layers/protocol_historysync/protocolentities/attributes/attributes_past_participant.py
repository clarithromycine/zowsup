from proto import e2e_pb2
from typing import Optional, Any, List, Dict, Union

class PastParticipantAttribute:

    def __init__(self,userJid,leaveReason,leaveTs) -> None:
        self.userJid = userJid
        self.leaveReason = leaveReason
        self.leaveTs = leaveTs


    def encode(self) -> Any:
        pb_obj  = e2e_pb2.PastParticipant()

        if self.userJid is not None:
            pb_obj.userJid = self.userJid
        
        if self.leaveReason is not None:            
            pb_obj.leaveReason = self.leaveReason

        if self.leaveTs is not None:            
            pb_obj.leaveTs = self.leaveTs

        return pb_obj
    

    @staticmethod
    def decodeFrom(pb_obj):
        
        userJid = pb_obj.userJid if pb_obj.HasField("userJid") else None

        leaveReason = pb_obj.leaveReason if pb_obj.HasField("leaveReason") else None

        leaveTs = pb_obj.leaveTs if pb_obj.HasField("leaveTs") else None
                
        return PastParticipantAttribute(
            userJid=userJid,
            leaveReason=leaveReason,
            leaveTs=leaveTs
        )
    









        

    
        
