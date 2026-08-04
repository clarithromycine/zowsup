from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .ack import AckProtocolEntity
from .ack_outgoing import OutgoingAckProtocolEntity

class IncomingAckProtocolEntity(AckProtocolEntity):

    '''
    <ack t="{{TIMESTAMP}}" from="{{FROM_JID}}" id="{{MESSAGE_ID}}" class="{{call | message | receipt | ?}}">
    </ack>
    '''

    def __init__(self, _id, _class, _from,timestamp, participant=None) -> None:
        super().__init__(_id, _class)
        self.setIncomingData(_from, timestamp,participant)        
        self.relay = None # preserved for VoIP relay extraction
        self._original_node = None  # preserved by fromProtocolTreeNode()        

    def setIncomingData(self, _from, timestamp,participant) -> Any:
        self._from = _from
        self.timestamp = timestamp
        self.participant = participant
    
    def getRelay(self):
        """Return the original ProtocolTreeNode with all children preserved."""
        return self.relay

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        node.setAttribute("from", self._from)
        node.setAttribute("t", self.timestamp)
        return node

    def getFrom(self) -> Any:
        return self._from
    
    def getParticipant(self) -> Any:
        return self.participant        


    def __str__(self):
        out  = super().__str__()
        out += "From: {}\n".format(self._from)
        out += "Timestamp: {}\n".format(self.timestamp)
        out += "Participant: {}\n".format(self.participant)
        return out
    
    def ack(self) -> Any:
        return OutgoingAckProtocolEntity(self.getId(), "receipt",self._type, self.getFrom(), participant = self.participant)        
    

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = AckProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = IncomingAckProtocolEntity
        entity.setIncomingData(
            node.getAttributeValue("from"),
            node.getAttributeValue("t"),
            node.getAttributeValue("participant")
        )
        entity._original_node = node  # preserve raw node for relay/rte extraction

        if entity.getClass() == "call" and entity.getType() == "offer":
            #这情况需要保留下面的relay信息
            relay = node.getChild("relay")  # preserve <relay> node for VoIP relay extraction            
            if relay is not None:
                #因为平时不常用，延迟加载吧
                from ....layers.protocol_calls.protocolentities.attributes.attributes_relay import RelayAttributes
                entity.relay = RelayAttributes.parse_from_node(relay)  # parse relay attributes from <relay> node

        return entity
