from proto import e2e_pb2
from typing import Optional, Any, List, Dict, Union

class HistorySyncNotificationAttribute:      
    def __init__(self,mediaSha256=None,mediaEncryptedSha256=None,mediaKey=None,mediaDirectPath=None,mediaSize=None,syncType=None) -> None:

        self.mediaSha256 = mediaSha256
        self.mediaEncryptedSha256 = mediaEncryptedSha256
        self.mediaKey = mediaKey
        self.mediaDirectPath = mediaDirectPath
        self.mediaSize = mediaSize
        self.syncType=syncType
                      

    def encode(self) -> Any:
        
        pb_obj = e2e_pb2.HistorySyncNotification()

        pb_obj.fileSha256 = self.mediaSha256
        pb_obj.fileEncSha256 = self.mediaEncryptedSha256
        pb_obj.mediaKey = self.mediaKey
        pb_obj.directPath = self.mediaDirectPath
        pb_obj.fileLength = self.mediaSize

        if self.syncType is not None:
            pb_obj.syncType=self.syncType

        return pb_obj
    
    @staticmethod
    def decodeFrom(pb_obj):

        mediaSha256 = pb_obj.fileSha256 if pb_obj.HasField("fileSha256") else None
        mediaEncryptedSha256 = pb_obj.fileEncSha256 if pb_obj.HasField("fileEncSha256") else None
        mediaKey = pb_obj.mediaKey if pb_obj.HasField("mediaKey") else None
        mediaDirectPath = pb_obj.directPath if pb_obj.HasField("directPath") else None
        mediaSize = pb_obj.fileLength if pb_obj.HasField("fileLength") else None
        syncType = pb_obj.syncType if pb_obj.HasField("syncType") else None
        
        return HistorySyncNotificationAttribute(
            mediaSha256 = mediaSha256,
            mediaEncryptedSha256=mediaEncryptedSha256,
            mediaKey=mediaKey,
            mediaDirectPath=mediaDirectPath,
            mediaSize=mediaSize,
            syncType=syncType
        ) 
        








        

    
        
