
from core.layers.protocol_calls.protocolentities.attributes import attributes_relay
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
from .attributes.attributes_relay import RelayAttributes


class OfferCallProtocolEntity(CallProtocolEntity):
    """
    Specialized CallProtocolEntity for "offer" type.
    

    主叫时，发送的offer消息示例：

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

    被叫时，offer里面会有relay

    <call from="248846345101511@lid" version="2.26.25.80" platform="android" id="920146C7BB2C26993F6497100E622DD7" notify="k.z" e="0" t="1783331927">
    <offer call-creator="248846345101511@lid" call-id="000853EF5247DC87B57BFEFF4DCADAC8" device_class="2016" caller_pn="8619874406144@s.whatsapp.net" joinable="1" caller_country_code="CN">
        <audio rate="16000" enc="opus" />
        <audio rate="8000" enc="opus" />
        <capability ver="1">
        0x0105f709e0fa13
        </capability>
        <enc v="2" type="msg">
        0x330a21059398274770f47636f806c5075e0cace481f687c0f9cf59ff773e95cb8fa07d4e100218002240837a02eb746024d9541102508cae28eebb78efafa46b5640c1837fb89b10c10a0ecbea3ebcd2916775054c9aeacd6aef59a34d9754a8d87bdc0d40f929e3b5281b034ffaac747d3c
        </enc>
        <encopt keygen="2" />
        <metadata peer_abtest_bucket="" peer_abtest_bucket_id_list="127466" />
        <net medium="3" />
        <rte>
        0x24010b60001600840000000000000000e1e2
        </rte>
        <uploadfieldstat />
        <voip_settings uncompressed="1">
        0x7b22616563223a7b226165636d5f61646170745f737465705f73697a65223a2232222c22616c676f726974686d223a226165636d5f6d3839222c22626572796c5f6165635f656e61626c65223a2266616c7365222c22626572796c5f6165635f6c61746573745f656e61626c65223a2274727565222c2264697361626c655f616763223a2231222c2265635f6f66665f7468726573686f6c64223a223430222c2265635f7468726573686f6c64223a223530222c226563686f5f636f6e666964656e63655f686973745f656e61626c6564223a2274727565222c226563686f5f6465746563746f725f696d706c223a2232222c226563686f5f6465746563746f725f6d6f6465223a2234222c226563686f5f7375705f6f70745f666978223a2274727565222c22656e61626c655f646966665f65635f6d657472696373223a2274727565222c226d6f6465223a2232222c226f6666736574223a2230222c2272756e5f6165635f666f6c6c6f7765645f62795f6e73223a2274727565222c22736b69705f7768656e5f6e6f5f6563686f223a2231222c227872615f6563686f5f6d6574726963735f656e61626c6564223a2274727565222c227872615f7072655f6563686f5f6d6574726963735f656e61626c6564223a2274727565227d2c22616763223a7b226167635f7573655f7765627274...[truncated 23234 bytes]
        </voip_settings>
        <relay attribute_padding="1" peer_pid="1" self_pid="0" uuid="xFGXvPWtAHmVOUPO">
            <participant pid="1" jid="248846345101511@lid" />
            <token id="0">
                0x090f01f5413f044f16427eeeb5220f6a8a10cb971a90845afe68ae136b147388ac423ddbf039bb19650a11e88b903280512d72f96163952a499553fb245f419f7294c46df6139efd84e1ae1dbb7eeddda19565f599b7b86b9ecdb099023ecb879cf91b3678cffd3b3a57e8e9af0617ec9cc4bbf35dab40d4d54e375e0bb4d574f40f4833d51dfacb52784446b9fb0e85206eb1da491f22a31e3860b334f8c9504c1f75525023bb884c24e59fadb455673aa2d88b6a20e16492edebaa9a9528
            </token>
            <token id="1">
                0x090f01f59fc43c9275ee4542f112875c018921c2c2ae122fc36b6996ba26d2eeb0bf97d29dac8fef1e668fd27b77bc2a4f77dae04bc133bdcc5ef45d0d47d02486bd092642ee74442b0d4d3e32a05ec718a8326ebc85763c2bee2bc63f9221e27a5620da5fd4ccb5e3ac5786cf7973511009ee0384ffa6fa1c6cba3a42e3053fac3c5f3a5ae19c7650c875ae4a0080ecae88a5fd354c4520c96267bcebd48ac97047f53320018db047f1ae457ddf05479fd8a5627648dc495ca31ac5a3ad10
            </token>
            <token id="2">
                0x090f01f5c375aa61d2f54c285decb517357e62ae584ef3555e444571bfcdc833af5a3ba5c91f6d64e6734bbf787b091142bb61a29169b1417a3eb9c679410d3ee128459e75c5155ff0de095a47987e7f4706cdcc3f941b29c030c745f928a106faabb74d8caa856a89385a40487bce04d40d8ad904baa49844791ab34f80cf14c40e5a17af32cd30161aea20dea438a4971db026c267b4e0316a198408537c4ea81355c2bed0eb7449003ea06969e6a014213456105af1c06477c685af008c
            </token>
            <key>
                0x65685830677774726e636265386a514e714175614b513d3d
            </key>
            <te2 protocol="1" relay_name="nrt6c01" c2r_rtt="55" relay_id="0" token_id="1">
                0x39902d360d96
            </te2>
            <te2 protocol="1" relay_name="nrt6c01" c2r_rtt="55" relay_id="0" token_id="1">
                0x2a032880f3130136faceb00c000000b10d96
            </te2>
            <te2 relay_name="nrt6c01" c2r_rtt="55" relay_id="0" token_id="1">
                0x39902d360d96
            </te2>
            <te2 relay_name="nrt6c01" c2r_rtt="55" relay_id="0" token_id="1">
                0x2a032880f3130136faceb00c000000b10d96
            </te2>
            <te2 protocol="1" relay_name="itm1c01" c2r_rtt="53" relay_id="1" token_id="0">
                0x9df0d13e0d96
            </te2>
            <te2 protocol="1" relay_name="itm1c01" c2r_rtt="53" relay_id="1" token_id="0">
                0x2a032880f24e00c0faceb00c000001770d96
            </te2>
            <te2 relay_name="itm1c01" c2r_rtt="53" relay_id="1" token_id="0">
                0x9df0d13e0d96
            </te2>
            <te2 relay_name="itm1c01" c2r_rtt="53" relay_id="1" token_id="0">
                0x2a032880f24e00c0faceb00c000001770d96
            </te2>
            <te2 protocol="1" relay_name="sin2c01" c2r_rtt="36" relay_id="2" token_id="2">
                0x399099360d96
            </te2>
            <te2 protocol="1" relay_name="sin2c01" c2r_rtt="36" relay_id="2" token_id="2">
                0x2a032880f34c0136faceb00c000000b10d96
            </te2>
            <te2 relay_name="sin2c01" c2r_rtt="36" relay_id="2" token_id="2">
                0x399099360d96
            </te2>
            <te2 relay_name="sin2c01" c2r_rtt="36" relay_id="2" token_id="2">
                0x2a032880f34c0136faceb00c000000b10d96
            </te2>
            <hbh_key>
                0x434f396139715162534b7a554c685673724b723837444a6762514a32384671472b4c5757382b5a63
            </hbh_key>
        </relay>
    </offer>
    </call>    
    
    """

    def __init__(self,callId=None,callCreator=None,deviceClass=None,callerPn=None,joinable=None,callerCountryCode=None,privacy=None,audioList=None,netMedium=None,capabilityVer=None,capabilityData=None,encoptKeygen=None,metaData=None,destinationJids=None,callKey=None,relay=None,rte=None,callMetaAttributes=None,db=None) -> None:
        
        super().__init__("offer",callCreator=callCreator,callId=callId,callMetaAttributes=callMetaAttributes)

        self.deviceClass = deviceClass or "2015"
        self.callerPn = callerPn
        self.joinable = joinable    
        self.callerCountryCode = callerCountryCode

        self.privacy = privacy 
        self.audioList = audioList or [{"rate": "8000", "enc": "opus"},{"rate": "16000", "enc": "opus"}]  
        self.netMedium = netMedium or "3" 
        self.capabilityVer = capabilityVer or "1"
        self.capabilityData = capabilityData or base64.b64decode("AQX3CeT6Ew==")
        self.destinationJids = destinationJids or []
        self.encoptKeygen = encoptKeygen or "2"
        self.metaData = metaData or {"peer_abtest_bucket":"","peer_abtest_bucket_id_list":"125266,127542"}
        self.callKey = callKey
        self.relay = relay
        self.rte = rte or b""
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
        return self.destinationJids

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
            children.append(ProtocolTreeNode("privacy", data=self.privacy))
        
        for audio in self.audioList:
            children.append(ProtocolTreeNode("audio", {"rate": audio["rate"], "enc": audio["enc"]}))

        if self.netMedium is not None:
            children.append(ProtocolTreeNode("net", {"medium": self.netMedium}))

        if self.capabilityVer is not None and self.capabilityData is not None:
            children.append(ProtocolTreeNode("capability", {"ver": self.capabilityVer}, data=self.capabilityData))

        if self.encoptKeygen is not None:
            children.append(ProtocolTreeNode("encopt", {"keygen": self.encoptKeygen}))

        if self.metaData is not None:
            children.append(ProtocolTreeNode("metadata", self.metaData))
                        

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
    
    @staticmethod
    def fromProtocolTreeNode(node: ProtocolTreeNode, db: Any) -> 'CallOffer':        
        """Parse a <call> ProtocolTreeNode containing an <offer> child into CallOffer."""
        offer_node = node.getChild("offer")
        if offer_node is None:
            raise ValueError("Not an offer call: missing <offer> child")

        call_creator = offer_node.getAttributeValue("call-creator")
        call_id = offer_node.getAttributeValue("call-id")
        device_class = offer_node.getAttributeValue("device_class")
        caller_pn = offer_node.getAttributeValue("caller_pn")
        joinable = offer_node.getAttributeValue("joinable")
        caller_country_code = offer_node.getAttributeValue("caller_country_code")


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

        meta_data = None
        meta_node = offer_node.getChild("metadata")
        if meta_node:
            meta_data = {k: v for k, v in meta_node.attributes.items()}


        call_key = None
        enc_node = offer_node.getChild("enc")

        if enc_node:
            type = enc_node.getAttributeValue("type")
            jid = node["from"]

            if jid:
                enc_data = enc_node.getData()

                try:
                    text = db.decrypt_msg(jid, enc_data, True) if type == "msg" else db.decrypt_pkmsg(jid, enc_data, True)
                    e2e_msg = e2e_pb2.Message()
                    e2e_msg.ParseFromString(text)
                    call_key = e2e_msg.call.call_key
                except Exception as e:
                    pass

        
        relay = None
        relay_node =  offer_node.getChild("relay")
        if relay_node is not None:
            relay = RelayAttributes.parse_from_node(relay_node) if relay_node else None            

        # Extract rte from the offer (child of <offer>)
        rte_data = b""
        rte_node = offer_node.getChild("rte")
        if rte_node:
            rte_data = rte_node.getData() or b""

                            
        entity = OfferCallProtocolEntity(
            callId=call_id,
            callCreator=call_creator,            
            deviceClass=device_class,
            callerPn=caller_pn,
            joinable=joinable,
            callerCountryCode=caller_country_code,
            privacy=privacy,
            audioList=audio_list,                    
            netMedium=net_medium,
            capabilityVer=capability_ver,
            capabilityData=capability_data,
            encoptKeygen=encopt_keygen,
            metaData=meta_data,
            callKey=call_key,    
            relay = relay,
            rte = rte_data,
            callMetaAttributes=CallMetaAttributes.from_call_protocoltreenode(node),
            db=db,
        )
        return entity
