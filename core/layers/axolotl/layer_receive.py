from .layer_base import AxolotlBaseLayer
from typing import Optional, Any, List, Dict, Union

from ...layers.protocol_receipts.protocolentities import OutgoingReceiptProtocolEntity
from proto.e2e_pb2 import Message
from ...layers.axolotl.protocolentities import *
from ...layers.protocol_messages.protocolentities.proto import ProtoProtocolEntity
from ...layers.axolotl.props import PROP_IDENTITY_AUTOTRUST
from ...axolotl import exceptions

from axolotl.untrustedidentityexception import UntrustedIdentityException

import logging
logger = logging.getLogger(__name__)


class AxolotlReceivelayer(AxolotlBaseLayer):
    def __init__(self) -> None:
        super().__init__()
        self.v2Jids = [] #people we're going to send v2 enc messages
        self.sessionCiphers = {}
        self.groupCiphers = {}
        self.pendingIncomingMessages = {} #(jid, participantJid?) => message
        self._retries = {}

    async def receive(self, protocolTreeNode) -> Any:
        """
        :type protocolTreeNode: ProtocolTreeNode
        """        
        if not await self.processIqRegistry(protocolTreeNode):            
            if protocolTreeNode.tag == "message":
                await self.onMessage(protocolTreeNode)
            elif not protocolTreeNode.tag == "receipt":
                #receipts will be handled by send layer                
                await self.toUpper(protocolTreeNode)            

    async def processPendingIncomingMessages(self, jid, participantJid = None) -> Any:
        conversationIdentifier = (jid, participantJid)
        if conversationIdentifier in self.pendingIncomingMessages:
            for messageNode in self.pendingIncomingMessages[conversationIdentifier]:
                await self.onMessage(messageNode)

            del self.pendingIncomingMessages[conversationIdentifier]

    async def onMessage(self, protocolTreeNode) -> Any:          
        encNode = protocolTreeNode.getChild("enc")                
        if encNode:            
            await self.handleEncMessage(protocolTreeNode)
        else:
            await self.toUpper(protocolTreeNode)

    async def handleEncMessage(self, node) -> Any:                                
        encMessageProtocolEntity = EncryptedMessageProtocolEntity.fromProtocolTreeNode(node)       
        isGroup =  node["participant"] is not None
        senderJid = node["participant"] if isGroup else node["from"]
        if node.getChild("enc")["v"] == "2" and node["from"] not in self.v2Jids:
            self.v2Jids.append(node["from"])
        try:
            handled = False                        
            if encMessageProtocolEntity.getEnc(EncProtocolEntity.TYPE_SKMSG):                
                handled = await self.handleSenderKeyMessage(node)                           
                           
            if not handled:                                                                 
                if encMessageProtocolEntity.getEnc(EncProtocolEntity.TYPE_PKMSG):
                    await self.handlePreKeyWhisperMessage(node)                    
                elif encMessageProtocolEntity.getEnc(EncProtocolEntity.TYPE_MSG):
                    await self.handleWhisperMessage(node)                          
                else:
                    #兜底处理
                    await self.toLower(OutgoingReceiptProtocolEntity(node["id"], node["from"], participant=node["participant"]).toProtocolTreeNode())              

            self.reset_retries(node["id"])

        except exceptions.InvalidKeyIdException:
            logger.warning("Invalid KeyId for {}, going to send the receipt to ignore subsequence push".format(encMessageProtocolEntity.getAuthor(False)))
            await self.toLower(OutgoingReceiptProtocolEntity(node["id"], node["from"], participant=node["participant"]).toProtocolTreeNode())
                   
            
        except exceptions.InvalidMessageException:
            logger.warning("InvalidMessage for {}".format(encMessageProtocolEntity.getAuthor(False)))     
            if node["id"] in self._retries and self._retries[node["id"]] >=3:
                #重复三次，如果都是invalid可能是对方的异常，放弃,也有可能是本地的prekey变更，导致对方用的key无法解密
                await self.toLower(OutgoingReceiptProtocolEntity(node["id"], node["from"], participant=node["participant"]).toProtocolTreeNode())   
            else:            
                #time.sleep(1) 
                await self.send_retry(node, self.manager.registration_id)                

        except exceptions.NoSessionException:            
            logger.warning("No session for {}, getting their keys now".format(encMessageProtocolEntity.getAuthor(False)))   
            #self.toLower(OutgoingReceiptProtocolEntity(node["id"], node["from"], participant=node["participant"]).toProtocolTreeNode())  

            conversationIdentifier = (node["from"], node["participant"])

            if conversationIdentifier not in self.pendingIncomingMessages:
                self.pendingIncomingMessages[conversationIdentifier] = []
            self.pendingIncomingMessages[conversationIdentifier].append(node)

            successFn = lambda successJids, b: self.processPendingIncomingMessages(*conversationIdentifier) if len(successJids) else None

            errorFn = lambda err,b: self.toLower(OutgoingReceiptProtocolEntity(node["id"], node["from"], participant=node["participant"]).toProtocolTreeNode())   

            await self.getKeysFor([encMessageProtocolEntity.getAuthor(True)], successFn,errorFn)
        except exceptions.DuplicateMessageException:
            logger.warning("Received a message that we've previously decrypted, "
                           "going to send the delivery receipt myself")        
            await self.toLower(OutgoingReceiptProtocolEntity(node["id"], node["from"], participant=node["participant"]).toProtocolTreeNode())    

        except UntrustedIdentityException as e:
            if self.getProp(PROP_IDENTITY_AUTOTRUST, False):
                logger.warning("Autotrusting identity for {}".format(e.getName()))
                self.manager.trust_identity(e.getName(), e.getIdentityKey())
                return await self.handleEncMessage(node)
            else:                
                logger.error("Ignoring message with untrusted identity")
                await self.toLower(OutgoingReceiptProtocolEntity(node["id"], node["from"], participant=node["participant"]).toProtocolTreeNode())    

    def handleMsMessage(self,node) -> Any:

        pass

        '''
        msMessageProtocolEntity = EncryptedMessageProtocolEntity.fromProtocolTreeNode(node)
        enc = msMessageProtocolEntity.getEnc(EncProtocolEntity.TYPE_MSMSG)
        plaintext = self.manager.decrypt_msg(msMessageProtocolEntity.getAuthor(False), enc.getData(),
                                               enc.getVersion() == 2)

        if enc.getVersion() == 2:
            self.parseAndHandleMessageProto(msMessageProtocolEntity, plaintext)

        node = msMessageProtocolEntity.toProtocolTreeNode()
        print(node)
        node.addChild((ProtoProtocolEntity(plaintext, enc.getMediaType())).toProtocolTreeNode())
        '''


    async def handlePreKeyWhisperMessage(self, node) -> Any:
        pkMessageProtocolEntity = EncryptedMessageProtocolEntity.fromProtocolTreeNode(node)
        enc = pkMessageProtocolEntity.getEnc(EncProtocolEntity.TYPE_PKMSG)
        plaintext = self.manager.decrypt_pkmsg(pkMessageProtocolEntity.getAuthor(True), enc.getData(),
                                               enc.getVersion() == 2)

        if enc.getVersion() == 2:
            self.parseAndHandleMessageProto(pkMessageProtocolEntity, plaintext)

        node = pkMessageProtocolEntity.toProtocolTreeNode()
        node.addChild((ProtoProtocolEntity(plaintext, enc.getMediaType())).toProtocolTreeNode())


        await self.toUpper(node)

    async def handleWhisperMessage(self, node) -> Any:
        encMessageProtocolEntity = EncryptedMessageProtocolEntity.fromProtocolTreeNode(node)

        enc = encMessageProtocolEntity.getEnc(EncProtocolEntity.TYPE_MSG)
        plaintext = self.manager.decrypt_msg(encMessageProtocolEntity.getAuthor(True), enc.getData(),
                                             enc.getVersion() == 2)

        if enc.getVersion() == 2:
            self.parseAndHandleMessageProto(encMessageProtocolEntity, plaintext)

        node = encMessageProtocolEntity.toProtocolTreeNode()
        node.addChild((ProtoProtocolEntity(plaintext, enc.getMediaType())).toProtocolTreeNode())

        await self.toUpper(node)

    async def handleSenderKeyMessage(self, node) -> Any:
        encMessageProtocolEntity = EncryptedMessageProtocolEntity.fromProtocolTreeNode(node)
        enc = encMessageProtocolEntity.getEnc(EncProtocolEntity.TYPE_SKMSG)

        try:
            plaintext = self.manager.group_decrypt(
                groupid=encMessageProtocolEntity.getFrom(True),
                participantid=encMessageProtocolEntity.getAuthor(True),
                data=enc.getData()
            )
            self.parseAndHandleMessageProto(encMessageProtocolEntity, plaintext)
            node = encMessageProtocolEntity.toProtocolTreeNode()
            node.addChild((ProtoProtocolEntity(plaintext, enc.getMediaType())).toProtocolTreeNode())
            await self.toUpper(node)
            return True
        except exceptions.NoSessionException:
            logger.warning("Got retry to {}, going to send a retry".format(encMessageProtocolEntity.getAuthor(False)))
            if node["id"] in self._retries and self._retries[node["id"]] >= 3:
                logger.warning("Too many retries for group msg from {}, giving up".format(encMessageProtocolEntity.getAuthor(False)))
                await self.toLower(OutgoingReceiptProtocolEntity(node["id"], node["from"], participant=node["participant"]).toProtocolTreeNode())
            else:
                await self.send_retry(node, self.manager.registration_id)
            return True  # handled — prevent fallback plain receipt in handleEncMessage

    def parseAndHandleMessageProto(self, encMessageProtocolEntity, serializedData) -> Any:
        m = Message()
        try:
            m.ParseFromString(serializedData)
        except Exception:
            logger.error("DUMP: {}".format(serializedData))
            logger.error("bytes: {}".format([s for s in serializedData]))
            raise
        if not m or not serializedData:
            raise exceptions.InvalidMessageException()

        if m.HasField("sender_key_distribution_message"):
            self.handleSenderKeyDistributionMessage(
                m.sender_key_distribution_message,
                encMessageProtocolEntity.getAuthor(True)
            )

    def handleSenderKeyDistributionMessage(self, senderKeyDistributionMessage, participantId) -> Any:
        groupId = senderKeyDistributionMessage.group_id
        self.manager.group_create_session(
            groupid=groupId,
            participantid=participantId,
            skmsgdata=senderKeyDistributionMessage.axolotl_sender_key_distribution_message
        )

    async def send_retry(self, message_node, registration_id) -> Any:
        message_id = message_node["id"]
        if message_id in self._retries:
            count = self._retries[message_id]
            count += 1
        else:
            count = 1
        self._retries[message_id] = count
        retry = RetryOutgoingReceiptProtocolEntity.fromMessageNode(message_node, registration_id)
        retry.count = count
        await self.toLower(retry.toProtocolTreeNode())

    def reset_retries(self, message_id) -> Any:
        if message_id in self._retries:
            del self._retries[message_id]
