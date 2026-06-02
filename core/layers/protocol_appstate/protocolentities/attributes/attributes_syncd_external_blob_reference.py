from proto import protocol_pb2
from typing import Optional, Any, List, Dict, Union
from .....layers.protocol_appstate.protocolentities.attributes import *

class SyncdExternalBlobReferenceAttribute:
    def __init__(self, mediaKey,directPath,handle,fileSizeBytes,fileSha256,fileEncSha256) -> None:

        self.mediaKey = mediaKey
        self.directPath= directPath
        self.handle = handle
        self.fileSizeBytes = fileSizeBytes
        self.fileSha256 = fileSha256
        self.fileEncSha256 = fileEncSha256        
    
    def encode(self) -> Any:
        pb_obj = protocol_pb2.ExternalBlobReference()

        if self.mediaKey is not None:
            pb_obj.mediaKey = self.mediaKey
            
        if self.directPath is not None:
            pb_obj.directPath = self.directPath

        if self.handle is not None:
            pb_obj.handle = self.handle

        if self.fileSizeBytes is not None:
            pb_obj.fileSizeBytes = self.fileSizeBytes

        if self.fileSha256 is not None:
            pb_obj.fileSha256 = self.fileSha256

        if self.fileEncSha256 is not None:
            pb_obj.fileEncSha256 = self.fileEncSha256

        return pb_obj

    @staticmethod
    def decodeFrom(pb_obj):
        mediaKey = pb_obj.mediaKey if pb_obj.HasField("mediaKey") else None    
        directPath = pb_obj.directPath if pb_obj.HasField("directPath") else None 
        handle = pb_obj.handle if pb_obj.HasField("handle") else None 
        fileSizeBytes = pb_obj.fileSizeBytes if pb_obj.HasField("fileSizeBytes") else None 
        fileSha256 = pb_obj.fileSha256 if pb_obj.HasField("fileSha256") else None 
        fileEncSha256 = pb_obj.fileEncSha256 if pb_obj.HasField("fileEncSha256") else None 

        return SyncdExternalBlobReferenceAttribute(
            mediaKey=mediaKey,
            directPath=directPath,
            handle=handle,
            fileSizeBytes=fileSizeBytes,
            fileSha256=fileSha256,
            fileEncSha256=fileEncSha256
        )
