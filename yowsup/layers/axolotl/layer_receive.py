from .layer_base import AxolotlBaseLayer

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
    def __init__(self):
        super(AxolotlReceivelayer, self).__init__()
        self.v2Jids = [] #people we're going to send v2 enc messages
        self.sessionCiphers = {}
        self.groupCiphers = {}
        self.pendingIncomingMessages = {} #(jid, participantJid?) => message
        self._retries = {}

    def receive(self, protocolTreeNode):
        """
        :type protocolTreeNode: ProtocolTreeNode
        """        
        if not self.processIqRegistry(protocolTreeNode):            
            if protocolTreeNode.tag == "message":
                self.onMessage(protocolTreeNode)
            elif not protocolTreeNode.tag == "receipt":
                #receipts will be handled by send layer                
                self.toUpper(protocolTreeNode)            

    def processPendingIncomingMessages(self, jid, participantJid = None):
        conversationIdentifier = (jid, participantJid)
        if conversationIdentifier in self.pendingIncomingMessages:
            for messageNode in self.pendingIncomingMessages[conversationIdentifier]:
                self.onMessage(messageNode)

            del self.pendingIncomingMessages[conversationIdentifier]

    def onMessage(self, protocolTreeNode):          
        encNode = protocolTreeNode.getChild("enc")                
        if encNode:            
            self.handleEncMessage(protocolTreeNode)
        else:
            self.toUpper(protocolTreeNode)

    def handleEncMessage(self, node):                                
        encMessageProtocolEntity = EncryptedMessageProtocolEntity.fromProtocolTreeNode(node)       
        isGroup =  node["participant"] is not None
        senderJid = node["participant"] if isGroup else node["from"]
        if node.getChild("enc")["v"] == "2" and node["from"] not in self.v2Jids:
            self.v2Jids.append(node["from"])
        try:
            handled = False
            if encMessageProtocolEntity.getEnc(EncProtocolEntity.TYPE_SKMSG):
                handled = self.handleSenderKeyMessage(node)               
                           
            if not handled:                                                                 
                if encMessageProtocolEntity.getEnc(EncProtocolEntity.TYPE_PKMSG):
                    self.handlePreKeyWhisperMessage(node)
                elif encMessageProtocolEntity.getEnc(EncProtocolEntity.TYPE_MSG):
                    self.handleWhisperMessage(node)             
                else:
                    #兜底处理
                    self.toLower(OutgoingReceiptProtocolEntity(node["id"], node["from"], participant=node["participant"]).toProtocolTreeNode())              

            self.reset_retries(node["id"])

        except exceptions.InvalidKeyIdException:
            logger.warning("Invalid KeyId for %s, going to send the receipt to ignore subsequence push", encMessageProtocolEntity.getAuthor(False))
            self.toLower(OutgoingReceiptProtocolEntity(node["id"], node["from"], participant=node["participant"]).toProtocolTreeNode())
                   
            
        except exceptions.InvalidMessageException:
            logger.warning("InvalidMessage for %s", encMessageProtocolEntity.getAuthor(False))     
            if node["id"] in self._retries and self._retries[node["id"]] >=3:
                #重复三次，如果都是invalid可能是对方的异常，放弃
                self.toLower(OutgoingReceiptProtocolEntity(node["id"], node["from"], participant=node["participant"]).toProtocolTreeNode())   
            else:            
                #time.sleep(1) 
                self.send_retry(node, self.manager.registration_id)                

        except exceptions.NoSessionException:            
            logger.warning("No session for %s, getting their keys now", encMessageProtocolEntity.getAuthor(False))
            #self.toLower(OutgoingReceiptProtocolEntity(node["id"], node["from"], participant=node["participant"]).toProtocolTreeNode())  

            conversationIdentifier = (node["from"], node["participant"])

            if conversationIdentifier not in self.pendingIncomingMessages:
                self.pendingIncomingMessages[conversationIdentifier] = []
            self.pendingIncomingMessages[conversationIdentifier].append(node)

            successFn = lambda successJids, b: self.processPendingIncomingMessages(*conversationIdentifier) if len(successJids) else None

            self.getKeysFor([senderJid], successFn)
        except exceptions.DuplicateMessageException:
            logger.warning("Received a message that we've previously decrypted, "
                           "going to send the delivery receipt myself")        
            self.toLower(OutgoingReceiptProtocolEntity(node["id"], node["from"], participant=node["participant"]).toProtocolTreeNode())    

        except UntrustedIdentityException as e:
            if self.getProp(PROP_IDENTITY_AUTOTRUST, False):
                logger.warning("Autotrusting identity for %s", e.getName())
                self.manager.trust_identity(e.getName(), e.getIdentityKey())
                return self.handleEncMessage(node)
            else:                
                logger.error("Ignoring message with untrusted identity")
                self.toLower(OutgoingReceiptProtocolEntity(node["id"], node["from"], participant=node["participant"]).toProtocolTreeNode())    

    def handleMsMessage(self,node):

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


    def handlePreKeyWhisperMessage(self, node):
        pkMessageProtocolEntity = EncryptedMessageProtocolEntity.fromProtocolTreeNode(node)
        enc = pkMessageProtocolEntity.getEnc(EncProtocolEntity.TYPE_PKMSG)
        plaintext = self.manager.decrypt_pkmsg(pkMessageProtocolEntity.getAuthor(True), enc.getData(),
                                               enc.getVersion() == 2)

        if enc.getVersion() == 2:
            self.parseAndHandleMessageProto(pkMessageProtocolEntity, plaintext)

        node = pkMessageProtocolEntity.toProtocolTreeNode()
        node.addChild((ProtoProtocolEntity(plaintext, enc.getMediaType())).toProtocolTreeNode())


        self.toUpper(node)

    def handleWhisperMessage(self, node):
        encMessageProtocolEntity = EncryptedMessageProtocolEntity.fromProtocolTreeNode(node)

        enc = encMessageProtocolEntity.getEnc(EncProtocolEntity.TYPE_MSG)
        plaintext = self.manager.decrypt_msg(encMessageProtocolEntity.getAuthor(False), enc.getData(),
                                             enc.getVersion() == 2)

        if enc.getVersion() == 2:
            self.parseAndHandleMessageProto(encMessageProtocolEntity, plaintext)

        node = encMessageProtocolEntity.toProtocolTreeNode()
        node.addChild((ProtoProtocolEntity(plaintext, enc.getMediaType())).toProtocolTreeNode())

        self.toUpper(node)

    def handleSenderKeyMessage(self, node):
        encMessageProtocolEntity = EncryptedMessageProtocolEntity.fromProtocolTreeNode(node)
        enc = encMessageProtocolEntity.getEnc(EncProtocolEntity.TYPE_SKMSG)

        try:
            plaintext = self.manager.group_decrypt (
                groupid=encMessageProtocolEntity.getFrom(True),
                participantid=encMessageProtocolEntity.getParticipant(False),
                data=enc.getData()
            )
            self.parseAndHandleMessageProto(encMessageProtocolEntity, plaintext)
            node = encMessageProtocolEntity.toProtocolTreeNode()
            node.addChild((ProtoProtocolEntity(plaintext, enc.getMediaType())).toProtocolTreeNode())
            self.toUpper(node)
            return True
        except exceptions.NoSessionException:
            logger.warning("Got retry to %s, going to send a retry", encMessageProtocolEntity.getAuthor(False))            
            return False

    def parseAndHandleMessageProto(self, encMessageProtocolEntity, serializedData):
        m = Message()
        try:
            m.ParseFromString(serializedData)
        except:
            print("DUMP:")
            print(serializedData)
            print([s for s in serializedData])
            raise
        if not m or not serializedData:
            raise exceptions.InvalidMessageException()

        if m.HasField("sender_key_distribution_message"):
            self.handleSenderKeyDistributionMessage(
                m.sender_key_distribution_message,
                encMessageProtocolEntity.getParticipant(False)
            )

    def handleSenderKeyDistributionMessage(self, senderKeyDistributionMessage, participantId):
        groupId = senderKeyDistributionMessage.group_id
        self.manager.group_create_session(
            groupid=groupId,
            participantid=participantId,
            skmsgdata=senderKeyDistributionMessage.axolotl_sender_key_distribution_message
        )

    def send_retry(self, message_node, registration_id):
        message_id = message_node["id"]
        if message_id in self._retries:
            count = self._retries[message_id]
            count += 1
        else:
            count = 1
        self._retries[message_id] = count
        retry = RetryOutgoingReceiptProtocolEntity.fromMessageNode(message_node, registration_id)
        retry.count = count
        self.toLower(retry.toProtocolTreeNode())

    def reset_retries(self, message_id):
        if message_id in self._retries:
            del self._retries[message_id]
