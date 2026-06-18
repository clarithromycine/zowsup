from ....structs import ProtocolEntity
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_receipts.protocolentities  import OutgoingReceiptProtocolEntity
from ....layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from copy import deepcopy
from core.common.tools import WATools
from core.common.tools import WATools

import traceback


class MessageProtocolEntity(ProtocolEntity):

    MESSAGE_TYPE_TEXT = "text"
    MESSAGE_TYPE_MEDIA = "media"

    def __init__(self, messageType, messageMetaAttributes) -> None:
        """
        :type messageType: str
        :type messageMetaAttributes: MessageMetaAttributes
        """
        super().__init__("message")
        assert type(messageMetaAttributes) is MessageMetaAttributes

        self._type = messageType        

        if messageMetaAttributes.id is None:
            messageMetaAttributes.id = ProtocolEntity.ID_TYPE_ANDROID


        if messageMetaAttributes.id in [0,1,2,3]:
            self._id = self._generateId(type=messageMetaAttributes.id)      
        else:
            self._id = messageMetaAttributes.id

        self._from = messageMetaAttributes.sender
        self.to = messageMetaAttributes.recipient
        self.timestamp = messageMetaAttributes.timestamp or self._getCurrentTimestamp()
        self.notify = messageMetaAttributes.notify
        self.offline = messageMetaAttributes.offline
        self.retry = messageMetaAttributes.retry
        self.participant= messageMetaAttributes.participant
        self.fromme = messageMetaAttributes.fromMe   
        self.category = messageMetaAttributes.category     
        self.phash = messageMetaAttributes.phash
        self.edit = messageMetaAttributes.edit
        
        self.sender_lid = messageMetaAttributes.sender_lid                
        self.sender_pn  = messageMetaAttributes.sender_pn
        self.peer_recipient_pn = messageMetaAttributes.peer_recipient_pn
        self.participant_pn = messageMetaAttributes.participant_pn

    def getFromMe(self) -> Any:
        return self.fromme        

    def getType(self) -> Any:
        return self._type

    def getEdit(self) -> Any:
        return self.edit

    def getId(self) -> Any:
        return self._id

    def getTimestamp(self) -> Any:
        return self.timestamp

    def getFrom(self, full = True, noDevice = False) -> Any:
        if full:
            #去掉jid中的deviceId部分，保持原有的格式不变，标准格式   number:deviceId@domain
            if noDevice:
                return self._from.split('@')[0].split(':')[0] + "@" + self._from.split('@')[1]            
            else:
                return self._from
                        
        # 清除掉@后面的部分，前面的部分如果有"."，把"."后面的部分也去掉，不指示deviceId
        return self._from.split('@')[0].split(':')[0]
    
    def isBroadcast(self) -> Any:
        return False

    def getTo(self, full = True) -> Any:
        return self.to if full else self.to.split('@')[0]

    def getParticipant(self, full = True) -> Any:
        if self.participant is None:
            return None
                
        return self.participant if full else self.participant.split('@')[0]
    
    def getParticipantPn(self, full = True) -> Any:
        if self.participant_pn is None:
            return None
        return self.participant_pn if full else self.participant_pn.split('@')[0]

    def getAuthor(self, full = True) -> Any:        

        if self.isGroupMessage(): 
            return self.getParticipantPn(full)  or self.getParticipant(full)
        
        _from = self.getFrom(full)
        
        a,b,c = WATools.jidDecode(_from)

        if _from.endswith("@lid"):
            return _from
                                
        if self.getSenderLid() is not None:            
            d,e,f = WATools.jidDecode(self.getSenderLid())
            return d+":"+str(c)+"@lid"
                        
        return a+"."+str(b)+":"+str(c)+"@s.whatsapp.net"
                    
    def getNotify(self) -> Any:
        return self.notify
    
    def getCategory(self) -> Any:
        return self.category
    
    def getSenderLid(self) -> Any:        
        return self.sender_lid
    
    def getSenderPn(self) -> Any:
        return self.sender_pn
    
    def getPeerRecipientPn(self) -> Any:
        return self.peer_recipient_pn


    def toProtocolTreeNode(self) -> Any:
        attribs = {
            "type"      : self._type,
            "id"        : self._id            
        }

        if self.category is not None:
            attribs["category"] = self.category

        if self.participant:
            attribs["participant"] = self.participant

        if self.isOutgoing():
            attribs["to"] = self.to
            #attribs["phash"] = "2:AIlF5031"            
            if (attribs["to"].endswith("@broadcast") or attribs["to"].endswith("g.us")) and self.phash is not None:      
                          
                attribs["phash"] = self.phash
            if self.category is not None:
                attribs["category"] = self.category
        else:
            attribs["from"] = self._from
            attribs["t"] = str(self.timestamp)
            if self.offline is not None:
               attribs["offline"] = "1" if self.offline else "0"
            if self.notify:
                attribs["notify"] = self.notify
            if self.retry:
                attribs["retry"] = str(self.retry)

        if self.edit:
            attribs["edit"] = self.edit

        if self.sender_lid:
            attribs["sender_lid"] = self.sender_lid

        if self.sender_pn:
            attribs["sender_pn"] = self.sender_pn

        if self.peer_recipient_pn:
            attribs["peer_recipient_pn"] = self.peer_recipient_pn
        
        xNode = None
        #if self.isOutgoing():
        #    serverNode = ProtocolTreeNode("server", {})
        #    xNode = ProtocolTreeNode("x", {"xmlns": "jabber:x:event"}, [serverNode])


        return self._createProtocolTreeNode(attribs, children = [xNode] if xNode else None, data = None)

    def isOutgoing(self) -> Any:
        return self._from is None

    def isGroupMessage(self) -> Any:
        if self.isOutgoing():
            return "-" in self.to
        return self.participant != None

    def __str__(self):
        out  = "Message:\n"
        out += "ID: {}\n".format(self._id)
        out += "To: {}\n".format(self.to) if self.isOutgoing() else "From: {}\n".format(self._from)
        out += "Type:  {}\n".format(self._type)
        out += "Timestamp: {}\n".format(self.timestamp)
        if self.participant:
            out += "Participant: {}\n".format(self.participant)
        return out

    def ack(self, read=False,histSync=False,peerMsg=False) -> Any:
        return OutgoingReceiptProtocolEntity(self.getId(), self.getFrom(), read, participant=self.getParticipant(),histSync=histSync,peerMsg=peerMsg)


    def forward(self, to, _id = None) -> Any:
        OutgoingMessage = deepcopy(self)
        OutgoingMessage.to = to
        OutgoingMessage._from = None
        OutgoingMessage._id = self._generateId() if _id is None else _id
        return OutgoingMessage

    @staticmethod
    def fromProtocolTreeNode(node,proto=None):                      
        return MessageProtocolEntity(
            node["type"],
            MessageMetaAttributes.from_message_protocoltreenode(node,proto)
        )
