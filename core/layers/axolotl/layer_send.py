from ...common import YowConstants
from typing import Optional, Any, List, Dict, Union
from ...layers.axolotl.no_target_exception import NoTargetException
from proto.e2e_pb2 import Message
from ...layers.axolotl.protocolentities import *
from ...layers.auth.layer_authentication import YowAuthenticationProtocolLayer
from ...layers.protocol_groups.protocolentities import InfoGroupsIqProtocolEntity, InfoGroupsResultIqProtocolEntity
from axolotl.protocol.whispermessage import WhisperMessage
from ...layers.protocol_messages.protocolentities.message import MessageMetaAttributes
from ...layers.axolotl.protocolentities.iq_keys_get_result import MissingParametersException
from ...layers.protocol_contacts.protocolentities  import *
from ...layers.protocol_contacts.protocolentities.iq_sync_devices import DevicesResultSyncIqProtocolEntity
from ...axolotl import exceptions
from .layer_base import AxolotlBaseLayer
from ...common.tools import WATools
from ...layers.protocol_acks.protocolentities.ack_incoming import IncomingAckProtocolEntity

from ...structs import  ProtocolTreeNode
import base64,os

import logging

logger = logging.getLogger(__name__)


class AxolotlSendLayer(AxolotlBaseLayer):
    MAX_SENT_QUEUE = 256

    def __init__(self) -> None:
        super().__init__()

        self.sessionCiphers = {}
        self.groupCiphers = {}
        '''
            Sent messages will be put in Queue until we receive a receipt for them.
            This is for handling retry receipts which requires re-encrypting and resend of the original message
            As the receipt for a sent message might arrive at a different yowsup instance,
            ideally the original message should be fetched from a persistent storage.
            Therefore, if the original message is not in sentQueue for any reason, we will
            notify the upper layers and let them handle it.
        '''
        self.sentQueue = []

    def __str__(self):
        return "Axolotl Layer"
    

    async def send(self, node) -> Any:          
        if node.tag == "message" and node["to"] not in self.skipEncJids:
            await self.processPlaintextNodeAndSend(node)
        else:
            await self.toLower(node)

    async def receive(self, protocolTreeNode) -> Any:
        async def on_get_keys_success(node, retry_entity, success_jids, errors):                        
            if len(errors):                
                self.on_get_keys_process_errors(errors)
            elif len(success_jids) == 1:                                        
                await self.processPlaintextNodeAndSend(node, retry_entity)
                #self.sendToContactsWithSessions(node, success_jids) 
                #self.sendToGroupWithSessions(node,None)
            else:
                raise NotImplementedError()

        if not await self.processIqRegistry(protocolTreeNode):
            if protocolTreeNode.tag == "receipt":
                '''
                Going to keep all group message enqueued, as we get receipts from each participant
                So can't just remove it on first receipt. Therefore, the MAX queue length mechanism should better be working
                '''
                messageNode = self.getEnqueuedMessageNode(protocolTreeNode["id"], protocolTreeNode["participant"] is not None)


                if  protocolTreeNode["type"] == "retry":
                    retryReceiptEntity = RetryIncomingReceiptProtocolEntity.fromProtocolTreeNode(protocolTreeNode)
                    await self.toLower(retryReceiptEntity.ack().toProtocolTreeNode()) #对重试那个包的ack，遵循协议    
                    if messageNode :
                        logger.info("Got retry to from {} for message {}, and Axolotl layer has the message".format(protocolTreeNode["from"],protocolTreeNode["id"]))
                        await self.getKeysFor(
                            [protocolTreeNode["participant"] or protocolTreeNode["from"]],
                            lambda successJids, errors: on_get_keys_success(messageNode, retryReceiptEntity, successJids, errors)
                        )         
                    else:
                        logger.debug("ignore retry receipt, because message not found in Axolotl")               

                else:
                    #logger.debug("bubbling non-retry-receipt upwards")
                    await self.toUpper(protocolTreeNode)                    


    def on_get_keys_process_errors(self, errors) -> Any:
        # type: (dict) -> None
        for jid, error in errors.items():
            if isinstance(error, MissingParametersException):
                logger.error("Failed to create prekeybundle for %s, user had missing parameters: %s, "
                             "is that a valid user?" % (jid, error.parameters))                
            elif isinstance(error, exceptions.UntrustedIdentityException):
                logger.error("Failed to create session for %s as user's identity is not trusted. " % jid)
            else:
                logger.error("Failed to process keys for %s, is that a valid user? Exception: %s" % error)

    async def processPlaintextNodeAndSend(self, node, retryReceiptEntity = None) -> Any:
            
        account,server = node["to"].split('@')        

        isGroup = YowConstants.WHATSAPP_GROUP_SERVER in node["to"] or  "broadcast" in node["to"]

        #isGroup= False

        async def on_iq_success(result, original_iq_entity): 
            entity =  DevicesResultSyncIqProtocolEntity.fromProtocolTreeNode(result)
            targets = entity.collectAllResultTargets()  # pylint: disable=no-member
            
            if len(targets)>0:
                node["to"] = targets[0]                         
                peer_recipient_pn = entity.getPnJid(targets[0])  # pylint: disable=no-member
                if peer_recipient_pn is not None:       
                    node["peer_recipient_pn"] = peer_recipient_pn
                
                await self.ensureSessionsAndSendToContacts(node, targets)
            else:
                logger.error("no target to send")

        def on_iq_error(entity, original_iq_entity): 
            logger.error("Failed to sync user devices")
                    
        
        if isGroup:                
            await self.sendToGroup(node, retryReceiptEntity)
        else:                                                       
            if ":" in account:
                #指定设备    
                accounts = [account]                    
                targets = [f"{r}@{server}" for r in accounts]

                await self.ensureSessionsAndSendToContacts(node, targets)                    
            else :                    
                #不指定设备，需要查客户所有的终端                                        
                entity = DevicesGetSyncIqProtocolEntity([node["to"]])
                await self._sendIq(entity, on_iq_success, on_iq_error)                                

    def enqueueSent(self, node) -> Any:
        logger.debug("enqueueSent(node=[omitted])")
        if len(self.sentQueue) >= self.__class__.MAX_SENT_QUEUE:
            logger.warn("Discarding queued node without receipt")
            self.sentQueue.pop(0)
        self.sentQueue.append(node)

    def getEnqueuedMessageNode(self, messageId, keepEnqueued = False) -> Any:
        for i in range(0, len(self.sentQueue)):
            if self.sentQueue[i]["id"] == messageId:
                if keepEnqueued:
                    return self.sentQueue[i]
                return self.sentQueue.pop(i)
            
    async def sendEncEntities(self, node, encEntities, participant=None,tctoken=None) -> Any:
        logger.debug("sendEncEntities(node=[omitted], encEntities=[omitted], participant=%s)" % participant)

        message_attrs = MessageMetaAttributes.from_message_protocoltreenode(node)
        message_attrs.participant = participant        
        messageEntity = EncryptedMessageProtocolEntity(
            encEntities,
            node["type"],
            message_attrs
        )
                
        # if participant is set, this message is directed to that specific participant as a result of a retry, therefore
        # we already have the original group message and there is no need to store it again.
        
        if participant is None:        
            self.enqueueSent(node)
            
        nodeSend = messageEntity.toProtocolTreeNode()
        #把biz节点复制转发

        if participant is None:        
            self.enqueueSent(node)

        nodeSend = messageEntity.toProtocolTreeNode()
        #把biz节点复制转发

        if node.getAttributeValue("category") == "peer":
            pass
        else:
            reporting = ProtocolTreeNode("reporting")
            reporting_token = ProtocolTreeNode("reporting_token",{"v":"2"})
            reporting_token.setData(os.urandom(16))            
            reporting.addChild(reporting_token)
            nodeSend.addChild(reporting)

        if tctoken:            
            tctoken = ProtocolTreeNode("tctoken",{},None,tctoken)
            nodeSend.addChild(tctoken)            

        biz = node.getChild("biz")
        if biz is not None:
            nodeSend.addChild(biz)

        profile = self.getProp("profile")
        if profile.config.device_identity is not None:                
            diddata = base64.b64decode(profile.config.device_identity)
            did = ProtocolTreeNode("device-identity", {},None,diddata)
            nodeSend.addChild(did)
        
        await self.toLower(nodeSend)


    async def sendToContact(self, node) -> Any:
        
        recipient_id = node["to"].split('@')[0]
        protoNode = node.getChild("proto")
        messageData = protoNode.getData()
        ciphertext = self.manager.encrypt(
            recipient_id,
            messageData
        )           

        mediaType = protoNode["mediatype"]
        return await self.sendEncEntities(node, [EncProtocolEntity(EncProtocolEntity.TYPE_MSG if ciphertext.__class__ == WhisperMessage else EncProtocolEntity.TYPE_PKMSG, 2, ciphertext.serialize(), mediaType)])

    async def ensureSessionsAndSendToContacts(self, node, targets) -> Any:

        logger.debug("ensureSessionsAndSendToContacts(node=[omitted], targets=%s)" % targets)
        targetToSend = []
        targetsWithoutSession = []

        standardTargets = []

        for target in targets:
            standardTargets.append(target.replace(".0:0","").replace(".1:",":").replace(":0",""))        

        for target in standardTargets:
            if not self.manager.session_exists(target):
                targetsWithoutSession.append(target)
            else:
                targetToSend.append(target)
        
        
        async def on_get_keys_success(node, success_jids, errors):                                    
            if len(errors):
                self.on_get_keys_process_errors(errors)
                return 

            targetToSend.extend(success_jids)

            #所有能成功建立session的，都发        
                   
            if len(success_jids)>0:
                if node.getAttributeValue("category")=="peer":                    
                    await self.sendToPeerWithSessions(node,targetToSend[0])
                else:
                    await self.sendToContactsWithSessions(node, targetToSend)

        if len(targetsWithoutSession):
            await self.getKeysFor(targetsWithoutSession, lambda successJids, errors: on_get_keys_success(node, successJids, errors))

        else:
            if node.getAttributeValue("category")=="peer":                    
                await self.sendToPeerWithSessions(node,targetToSend[0])
            else:
                await self.sendToContactsWithSessions(node, targetToSend) 

    async def sendToPeerWithSessions(self,node,jid) -> Any:    
    
        protoNode = node.getChild("proto")
        messageData = protoNode.getData()         
        ciphertext = self.manager.encrypt(
            jid.split('@')[0],                
            messageData                
        )             
        encEntities = [
            EncProtocolEntity(
                    EncProtocolEntity.TYPE_MSG if ciphertext.__class__ == WhisperMessage else EncProtocolEntity.TYPE_PKMSG
                , 2, ciphertext.serialize(), protoNode["mediatype"],  jid=None
            )
        ]       
        await self.sendEncEntities(node, encEntities)  


    async def sendToContactsWithSessions(self, node, targets, retryCount=0) -> Any:

        targets = targets or []
        targetJid = node["to"]
        db = self.getStack().getProp("profile").axolotl_manager
        
        tctoken = db._store.getTctoken(targetJid)        

        protoNode = node.getChild("proto")
        encEntities = []       
        messageData = protoNode.getData()        
        participant = targets[0] if len(targets) == 1 and retryCount > 0 else None         

        for target in targets:            
            messageData = protoNode.getData()
            
            ciphertext = self.manager.encrypt(
                target.split('@')[0],                
                messageData     
            )              
            
            encEntities.append(
                EncProtocolEntity(
                        EncProtocolEntity.TYPE_MSG if ciphertext.__class__ == WhisperMessage else EncProtocolEntity.TYPE_PKMSG
                    , 2, ciphertext.serialize(), protoNode["mediatype"],  jid=None if participant else target
                )
            )
        
        await self.sendEncEntities(node, encEntities, participant,tctoken)

    async def sendToGroupWithSessions(self, node, jidsNeedSenderKey = None, retryCount=0) -> Any:
        """
        For each jid in jidsNeedSenderKey will create a pkmsg enc node with the associated jid.
        If retryCount > 0 and we have only one jidsNeedSenderKey, this is a retry requested by a specific participant
        and this message is to be directed at specific at that participant indicated by jidsNeedSenderKey[0]. In this
        case the participant's jid would go in the parent's EncryptedMessage and not into the enc node.
        """
        logger.debug(
            "sendToGroupWithSessions(node=[omitted], jidsNeedSenderKey=%s, retryCount=%d)" % (jidsNeedSenderKey, retryCount)
        )
        jidsNeedSenderKey = jidsNeedSenderKey or []
        groupJid = node["to"]
        protoNode = node.getChild("proto")
        encEntities = []
        participant = jidsNeedSenderKey[0] if len(jidsNeedSenderKey) == 1 and retryCount > 0 else None 
        if len(jidsNeedSenderKey):
            senderKeyDistributionMessage = self.manager.group_create_skmsg(groupJid)
            for jid in jidsNeedSenderKey:
                message =  self.serializeSenderKeyDistributionMessageToProtobuf(node["to"], senderKeyDistributionMessage)
                if retryCount > 0:
                    message.MergeFromString(protoNode.getData())
                ciphertext = self.manager.encrypt(jid.split('@')[0], message.SerializeToString())
                encEntities.append(
                    EncProtocolEntity(
                            EncProtocolEntity.TYPE_MSG if ciphertext.__class__ == WhisperMessage else EncProtocolEntity.TYPE_PKMSG
                        , 2, ciphertext.serialize(), protoNode["mediatype"],  jid=None if participant else jid,count=str(retryCount)
                    )
                )

        if not retryCount:
            messageData = protoNode.getData()
            ciphertext = self.manager.group_encrypt(groupJid, messageData)
            mediaType = protoNode["mediatype"]
            encEntities.append(EncProtocolEntity(EncProtocolEntity.TYPE_SKMSG, 2, ciphertext, mediaType))

        await self.sendEncEntities(node, encEntities, participant)

    async def ensureSessionsAndSendToGroup(self, node, jids) -> Any:
        logger.debug("ensureSessionsAndSendToGroup(node=[omitted], jids=%s)" % jids)

        allJids = []
        jidsNoSession = []    
        standardJids = []
        for jid in jids:
            standardJids.append(jid.replace(".0:0","").replace(".1:",":"))

        for jid in standardJids:
            if not self.manager.session_exists(jid.split('@')[0]):          
                jidsNoSession.append(jid) #如果是xxxx.0:0, 规范是不加任何后缀，否则解码后就会对应不上)        
            else:
                allJids.append(jid)

        async def on_get_keys_success(node, success_jids, errors):
            if len(errors):
                self.on_get_keys_process_errors(errors)
            allJids.extend(success_jids)
            await self.sendToGroupWithSessions(node, allJids)
                        
        if len(jidsNoSession):
            await self.getKeysFor(jidsNoSession, lambda successJids, errors: on_get_keys_success(node, successJids, errors))
        else:
            await self.sendToGroupWithSessions(node, standardJids)

    async def sendToGroup(self, node, retryReceiptEntity = None) -> Any:
        """
        Group send sequence:
        check if senderkeyrecord exists
            no: - create,
                - get group jids from info request
                - for each jid without a session, get keys to create the session
                - send message with dist key for all participants
            yes:
                - send skmsg without any dist key

        received retry for a participant
            - request participants keys
            - send message with dist key only + conversation, only for this participat
        """
        logger.debug("sendToGroup(node=[omitted], retryReceiptEntity=[%s])" %
                     ("[retry_count={}, retry_jid={}]".format(
                         retryReceiptEntity.getRetryCount(), retryReceiptEntity.getRetryJid())
                      ) if retryReceiptEntity is not None else None)

        groupJid = node["to"]        
        ownJid = self.getLayerInterface(YowAuthenticationProtocolLayer).getUsername(True)
        senderKeyRecord = self.manager.load_senderkey(node["to"])

        async def sendToGroup(resultNode, requestEntity):
            groupInfo = InfoGroupsResultIqProtocolEntity.fromProtocolTreeNode(resultNode)
            jids = list(groupInfo.getParticipants().keys()) #keys in py3 returns dict_keys            
            if ownJid in jids:
                jids.remove(ownJid)            

            return await self.ensureSessionsAndSendToGroup(node, jids)

        if groupJid=="status@broadcast":            
            q = "SELECT recipient_id from identities WHERE recipient_id <> -1"        
            c = self._manager._store.identityKeyStore.dbConn.cursor()        
            c.execute(q)
            results = c.fetchall()
            jids = []
            for item in results:
                if isinstance(item[0],int):
                    jids.append(str(item[0])+"@s.whatsapp.net")            
            await self.ensureSessionsAndSendToGroup(node, jids)   

        elif groupJid.endswith("@broadcast"):
            jids = self._manager._store.findParticipantsByBcid(groupJid)            
            await self.ensureSessionsAndSendToGroup(node, jids)   

        elif senderKeyRecord.isEmpty():
            logger.debug("senderKeyRecord is empty, requesting group info")
            groupInfoIq = InfoGroupsIqProtocolEntity(groupJid)            
            await self._sendIq(groupInfoIq, sendToGroup)            
        else:
            logger.debug("We have a senderKeyRecord")
            retryCount = 0
            jidsNeedSenderKey = []
            if retryReceiptEntity is not None:
                retryCount = retryReceiptEntity.getRetryCount()
                jidsNeedSenderKey.append(retryReceiptEntity.getRetryJid())            
            await self.sendToGroupWithSessions(node, jidsNeedSenderKey, retryCount)

    def serializeSenderKeyDistributionMessageToProtobuf(self, groupId, senderKeyDistributionMessage, message = None) -> Any:
        m = message or Message()
        m.sender_key_distribution_message.group_id = groupId
        m.sender_key_distribution_message.axolotl_sender_key_distribution_message = senderKeyDistributionMessage.serialize()
        m.sender_key_distribution_message.axolotl_sender_key_distribution_message = senderKeyDistributionMessage.serialize()
        # m.conversation = text
        return m
    
