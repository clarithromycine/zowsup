
from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes
from core.layers.protocol_calls.protocolentities.with_proto import WithProtoProtocolEntity

from ....structs import ProtocolEntity, ProtocolTreeNode
from .call import CallProtocolEntity
from ....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict
import random
from proto import e2e_pb2
import base64,os
from axolotl.protocol.whispermessage import WhisperMessage


class OfferCallProtocolEntity(CallProtocolEntity):
    """
    Specialized CallProtocolEntity for "offer" type.
    
    <offer call-creator='61947068346426.1:0@lid' call-id='009A4B6DFAA4598...' device_class='2015'>
        <privacy>BAEvtFi+JSlVg3Y=</privacy>
        <audio rate='8000' enc='opus'/>
        <audio rate='16000' enc='opus'/>
        <net medium='3'/>
        <capability ver='1'>AQX3CeT6Ew==</capability>
        <destination>
            <to jid='1511:12@lid'><enc v='2' type='pkmsg'>...</enc></to>
            <to jid='1511:0@lid'><enc v='2' type='msg'>...</enc></to>
        </destination>
        <encopt keygen='2'/>
    </offer>
    """

    def __init__(self,callId=None,callCreator=None,deviceClass=None,callerPn=None,joinable=None,callerCountryCode=None,privacy=None,audioList=None,netMedium=None,destinationJids=None,callKey=None,callMetaAttributes=None,db=None) -> None:
        
        super().__init__("offer",callCreator=callCreator,callId=callId,callMetaAttributes=callMetaAttributes)

        self.deviceClass = deviceClass or "2015"
        self.callerPn = callerPn
        self.joinable = joinable    
        self.callerCountryCode = callerCountryCode

        self.privacy = privacy  # bytes (base64-encoded in XML)

        self.audioList = audioList or [{"rate": "8000", "enc": "opus"},{"rate": "16000", "enc": "opus"}]  
        self.netMedium = netMedium or "3" 
        self.capabilityVer = "1"
        self.capabilityData = "AQX3CeT6Ew=="  # (base64-encoded in XML)
        # destinations: [{"jid": "1511:12@lid", "enc_v": "2", "enc_type": "pkmsg", "enc_data": b"..."}, ...]
        self.destinationJids = destinationJids or []
        self.encoptKeygen = "2"
        self.callKey = callKey
        self.db = db

    def __repr__(self):
        return (
            f"CallOffer(call_id={self.getCallId()}, call_creator={self.call_creator}, "
            f"device_class={self.device_class}, audio={self.audio_list}, "
            f"net_medium={self.net_medium}, cap_ver={self.capability_ver}, "            
            f"encopt_keygen={self.encopt_keygen})"
        )

    # ── Accessors ──────────────────────────────────────────────


    def getDeviceClass(self) -> Optional[str]:
        return self.deviceClass

    def getPrivacy(self) -> Optional[bytes]:
        return self.privacy

    def getAudioList(self) -> List[Dict[str, str]]:
        return self.audioList

    def getNetMedium(self) -> Optional[str]:
        return self.netMedium

    def getCapability(self) -> Optional[tuple]:
        """Returns (ver: str, data: bytes) or None."""
        if self.capabilityVer is not None and self.capabilityData is not None:
            return (self.capabilityVer, self.capabilityData)
        return None

    def getDestinations(self) -> List[Dict[str, Any]]:
        return self.destinationContent

    def getEncoptKeygen(self) -> Optional[str]:
        return self.encoptKeygen


    # ── Serialization ──────────────────────────────────────────

    def toProtocolTreeNode(self) -> ProtocolTreeNode:
        """Override: serialize the full <call> with <offer> children."""

        node = super().toProtocolTreeNode()

        offerNode = node.getChild("offer")

        if self.deviceClass is not None:
            offerNode.setAttribute("device_class", self.deviceClass)
        
        children = []

        
        if self.privacy=="auto":
            self.privacy = self.db._store.getTctoken(self.destinationJids[0])

        if self.privacy is not None:                
            children.append(ProtocolTreeNode("privacy", data=base64.b64encode(self.privacy)))
        
        for audio in self.audioList:
            children.append(ProtocolTreeNode("audio", {"rate": audio["rate"], "enc": audio["enc"]}))

        if self.netMedium is not None:
            children.append(ProtocolTreeNode("net", {"medium": self.netMedium}))

        if self.capabilityVer is not None and self.capabilityData is not None:
            children.append(ProtocolTreeNode("capability", {"ver": self.capabilityVer}, data=self.capabilityData.encode()))

        if self.encoptKeygen is not None:
            children.append(ProtocolTreeNode("encopt", {"keygen": self.encoptKeygen}))

        pb = e2e_pb2.Message()
        pb.call.call_key = self.callKey or os.urandom(32)  # Generate a random call key if not provided
        text = pb.SerializeToString()

        destinationNode = ProtocolTreeNode("destination")

        for destinationJid in self.destinationJids:            
            ciphertext = self.db.encrypt(destinationJid,text)                 
            type = "msg" if ciphertext.__class__ == WhisperMessage else "pkmsg"
            data = ciphertext.serialize()                 
            enc_node = ProtocolTreeNode("enc", {"v": "2", "type": type}, data=data)
            to_node = ProtocolTreeNode("to", {"jid": destinationJid}, children=[enc_node])
            destinationNode.addChild(to_node)        
        children.append(destinationNode)        
        offerNode.addChildren(children)        
        return node


    # ── Deserialization ────────────────────────────────────────

    @staticmethod
    def fromProtocolTreeNode(node: ProtocolTreeNode, db: Any) -> 'CallOffer':
        """Parse a <call> ProtocolTreeNode containing an <offer> child into CallOffer."""
        offer_node = node.getChild("offer")
        if offer_node is None:
            raise ValueError("Not an offer call: missing <offer> child")

        call_creator = offer_node.getAttributeValue("call-creator")
        call_id = offer_node.getAttributeValue("call-id")
        device_class = offer_node.getAttributeValue("device_class")

        # <privacy>
        privacy = None
        privacy_node = offer_node.getChild("privacy")
        if privacy_node and privacy_node.getData():
            privacy = privacy_node.getData()

        # <audio> × N
        audio_list = []
        for audio_node in offer_node.getAllChildren("audio"):
            rate = audio_node.getAttributeValue("rate")
            enc = audio_node.getAttributeValue("enc")
            if rate and enc:
                audio_list.append({"rate": rate, "enc": enc})

        # <net>
        net_medium = None
        net_node = offer_node.getChild("net")
        if net_node:
            net_medium = net_node.getAttributeValue("medium")

        # <capability>
        capability_ver = None
        capability_data = None
        cap_node = offer_node.getChild("capability")
        if cap_node:
            capability_ver = cap_node.getAttributeValue("ver")
            if cap_node.getData():
                capability_data = cap_node.getData()


        # <encopt>
        encopt_keygen = None
        encopt_node = offer_node.getChild("encopt")
        if encopt_node:
            encopt_keygen = encopt_node.getAttributeValue("keygen")                

        
        enc_node = offer_node.getChild("enc")
        type = enc_node.getAttributeValue("type")
        jid = node["from"]

        
        if enc_node and jid:
            enc_data = enc_node.getData()
            text = db.decrypt_msg(jid, enc_data,True) if type=="msg" else db.decrypt_pkmsg(jid,enc_data,True)  # Decrypt the call key for this destination
            e2e_msg = e2e_pb2.Message()
            e2e_msg.ParseFromString(text)
            call_key = e2e_msg.call.call_key
                            
        return OfferCallProtocolEntity(
            callId=call_id,
            callCreator=call_creator,            
            deviceClass=device_class,
            privacy=privacy,
            audioList=audio_list,
            callKey=call_key,            
            netMedium=net_medium,                        
            # Base class fields
            callMetaAttributes=CallMetaAttributes.from_call_protocoltreenode(node),
            db = db
        )
