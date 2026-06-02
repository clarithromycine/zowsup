
from ....layers.protocol_messages.protocolentities.attributes.attributes_downloadablemedia import DownloadableMediaMessageAttributes
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_messages.protocolentities import *
from ....layers.protocol_messages.protocolentities.attributes import * 
from ....layers.protocol_historysync.protocolentities.attributes import *
from common.utils import Utils
class HistorySync:

    def __init__(self,media_conn,toJid) -> None:
        self.media_conn = media_conn
        self.toJid = toJid
        
    def createSyncMessage(self,history_sync_attrs,toJid,syncType="default") -> Any:

        syncBytes = Utils.compress(history_sync_attrs.encode().SerializeToString())
        media_attrs = DownloadableMediaMessageAttributes.from_buffer(syncBytes,"history-sync",self.media_conn)

        if syncType=="default":
            #榛樿鏄窡闅廰ttr鐨勭被鍨嬶紝闄ら潪鎸囧畾
            syncType = history_sync_attrs.syncType

        if toJid is None:
            #榛樿None鏄敤鏋勯€犲嚱鏁扮殑toJid锛岄櫎闈炴寚瀹?
            toJid = self.toJid 
       
        entity = ProtocolMessageProtocolEntity(protocol_attr=ProtocolAttributes(                    
            type = ProtocolAttributes.TYPE_HISTORY_SYNC_NOTIFICATION,
            history_sync_notification=HistorySyncNotificationAttribute(
                mediaSha256 = media_attrs.file_sha256,
                mediaEncryptedSha256 = media_attrs.file_enc_sha256,
                mediaKey = media_attrs.media_key,
                mediaDirectPath = media_attrs.direct_path,
                mediaSize = media_attrs.file_length,
                syncType=syncType
            )    
        ),message_meta_attributes=MessageMetaAttributes(
            recipient=toJid,
            category="peer"
        ))

        #杩斿洖杩欎釜锛屽灞傜洿鎺oLower灏卞彲浠?
        return entity
    

    '''
    #蹇€熸柟娉?
    '''

    def createNonBlockingDataMessage(self,toJid=None,pastParticipants=[]) -> Any:
       return self.createSyncMessage(
             history_sync_attrs=HistorySyncAttribute(
                            syncType = HistorySyncAttribute.NON_BLOCKING_DATA,
                            pastParticipants=pastParticipants
                        ),
             toJid = toJid,
             syncType = None
       )

    def createInitialStatusV3Message(self,toJid=None,statusV3Messages=[]) -> Any:
       return self.createSyncMessage(
             history_sync_attrs=HistorySyncAttribute(
                            syncType = HistorySyncAttribute.INITIAL_STATUS_V3,
                            statusV3Messages=statusV3Messages
                        ),
             toJid = toJid
       )
    
    def createPushNameMessage(self,toJid=None,pushnames=[]) -> Any:

        return self.createSyncMessage(
             history_sync_attrs=HistorySyncAttribute(
                            syncType = HistorySyncAttribute.PUSH_NAME,
                            pushnames=pushnames
                        ),
             toJid = toJid
       )

    def createRecentMessage(self,toJid=None,conversations=[]) -> Any:
        return self.createSyncMessage(
             history_sync_attrs=HistorySyncAttribute(
                            syncType = HistorySyncAttribute.RECENT,
                            conversations=conversations
                        ),
             toJid = toJid
       )

    def createInitialBootstrapMessage(self,toJid=None,conversations=[]) -> Any:
        return self.createSyncMessage(
             history_sync_attrs=HistorySyncAttribute(
                            syncType = HistorySyncAttribute.INITIAL_BOOTSTRAP,
                            conversations=conversations
                        ),
             toJid = toJid
       )

