"""
PreacceptCallProtocolEntity - <call><preaccept> stanza entity.

Sent by the callee after receiving an offer, to acknowledge receipt and
indicate that the media path is being prepared.

<call to="caller@s.whatsapp.net" id="STANZA_ID">
  <preaccept call-id="CALL_ID" call-creator="caller@s.whatsapp.net">
    <audio enc="opus" rate="16000"/>    
    <capability ver="1">0105ff09e4bb07</capability>
    <encopt keygen="2"/>
  </preaccept>
</call>

Reference: WaCalls internal/voip/signaling/signaling_build.go BuildPreacceptStanza()
"""

from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes
from ....structs import ProtocolTreeNode
from .call import CallProtocolEntity
from typing import Optional, List, Dict

class PreacceptCallProtocolEntity(CallProtocolEntity):
    """
    Specialized CallProtocolEntity for "preaccept" type.

    Unlike offer/accept, preaccept does NOT carry encrypted callKey.
    It is a simple acknowledgement sent by the callee.
    """

    def __init__(
        self,
        callId: Optional[str] = None,
        callCreator: Optional[str] = None,
        audioList: Optional[List[Dict[str, str]]] = None,
        encoptKeygen: Optional[str] = None,
        capabilityVer: Optional[str] = None,
        capabilityData: Optional[bytes] = None,
        callMetaAttributes: Optional[CallMetaAttributes] = None,
    ) -> None:
        super().__init__("preaccept", callCreator=callCreator, callId=callId, callMetaAttributes=callMetaAttributes)

        self.audioList = audioList or [{"rate": "16000", "enc": "opus"}]
        self.encoptKeygen = encoptKeygen or "2"        
        # Base64-encoded capability bytes for XML serialization
        import base64
        self.capabilityVer = capabilityVer or "1"
        self.capabilityData =  capabilityData or base64.b64decode("AQX3CeT6Ew==")

    def __repr__(self):
        return (
            f"PreacceptCall(call_id={self.getCallId()}, call_creator={self.getCallCreator()}, "
            f"audio={self.audioList}, net_medium={self.netMedium})"
        )

    # ── Accessors ──────────────────────────────────────────────

    def getAudioList(self) -> List[Dict[str, str]]:
        return self.audioList
    
    def getEncoptKeygen(self) -> Optional[str]:
        return self.encoptKeygen

    def getCapabilityVer(self) -> Optional[str]:
        return self.capabilityVer

    def getCapabilityData(self) -> Optional[bytes]:
        return self.capabilityData


    # ── Serialization ──────────────────────────────────────────

    def toProtocolTreeNode(self) -> ProtocolTreeNode:
        node = super().toProtocolTreeNode()
        preacceptNode = node.getChild("preaccept")

        children = [
            ProtocolTreeNode("audio", {"enc": "opus", "rate": "16000"}),            
            ProtocolTreeNode("capability", {"ver": self.capabilityVer}, data=self.capabilityData),
            ProtocolTreeNode("encopt", {"keygen": self.encoptKeygen}),
        ]
        preacceptNode.addChildren(children)
        return node

    # ── Deserialization ────────────────────────────────────────

    @staticmethod
    def fromProtocolTreeNode(node: ProtocolTreeNode) -> "PreacceptCallProtocolEntity":
        preaccept_node = node.getChild("preaccept")
        if preaccept_node is None:
            raise ValueError("Not a preaccept call: missing <preaccept> child")

        call_creator = preaccept_node.getAttributeValue("call-creator")
        call_id = preaccept_node.getAttributeValue("call-id")

        encopt_keygen = None
        encopt_node = preaccept_node.getChild("encopt")
        if encopt_node:
            encopt_keygen = encopt_node.getAttributeValue("keygen")                

        # <capability>
        capability_ver = None
        capability_data = None
        cap_node = preaccept_node.getChild("capability")
        if cap_node:
            capability_ver = cap_node.getAttributeValue("ver")
            if cap_node.getData():
                capability_data = cap_node.getData()


        return PreacceptCallProtocolEntity(
            callId=call_id,
            callCreator=call_creator,
            encoptKeygen=encopt_keygen,
            capabilityVer=capability_ver,
            capabilityData=capability_data,
            callMetaAttributes=CallMetaAttributes.from_call_protocoltreenode(node),
        )
