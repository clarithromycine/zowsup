"""
AcceptCallProtocolEntity - <call><accept> stanza entity.

Sent by the callee to accept an incoming call. Carries an E2E-encrypted
callKey (using Signal Protocol) for the call-creator's device.

<call to="caller@s.whatsapp.net" id="STANZA_ID">
  <accept call-id="CALL_ID" call-creator="caller@s.whatsapp.net">
    <audio enc="opus" rate="16000"/>
    <net medium="3"/>
    <enc v="2" type="msg|pkmsg">...Signal Protocol encrypted callKey...</enc>
    <encopt keygen="2"/>
  </accept>
</call>

Key difference from offer: accept sends enc node directly under <accept>
(not wrapped in <destination><to>), and only encrypts for the call-creator.

Reference: WaCalls internal/voip/signaling/signaling_build.go BuildAcceptStanza()
"""

from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes
from ....structs import ProtocolTreeNode
from .call import CallProtocolEntity
from typing import Optional, Any, List, Dict
import os
from proto import e2e_pb2
from axolotl.protocol.whispermessage import WhisperMessage


class AcceptCallProtocolEntity(CallProtocolEntity):
    """
    Specialized CallProtocolEntity for "accept" type.

    When building: encrypts the callKey via Signal Protocol for the call-creator.
    When parsing: decrypts the callKey from the <enc> node.
    """

    def __init__(
        self,
        callId: Optional[str] = None,
        callCreator: Optional[str] = None,
        callKey: Optional[bytes] = None,
        audioList: Optional[List[Dict[str, str]]] = None,
        netMedium: Optional[str] = None,
        encoptKeygen: Optional[str] = None,
        metaData: Optional[Dict[str, str]] = None,
        callMetaAttributes: Optional[CallMetaAttributes] = None,
        db: Any = None,
    ) -> None:
        """
        :param callId: WhatsApp call ID
        :param callCreator: JID of the call creator
        :param callKey: 32-byte raw call key (will be E2E encrypted for the creator)
        :param audioList: list of audio capability dicts
        :param netMedium: network medium (default "3")
        :param encoptKeygen: key generation method (default "2")
        :param callMetaAttributes: stanza-level metadata
        :param db: axolotl_manager for E2E encryption/decryption
        """
        super().__init__("accept", callCreator=callCreator, callId=callId, callMetaAttributes=callMetaAttributes)

        self.callKey = callKey
        self.audioList = audioList or [{"rate": "16000", "enc": "opus"}]
        self.netMedium = netMedium or "3"
        self.encoptKeygen = encoptKeygen or "2"
        self.metaData = metaData or {"peer_abtest_bucket_id_list": "125266,127542"}
        self.db = db
        self.te_candidates = []  # ICE candidates: [{"priority": str, "data": bytes}]

    def __repr__(self):
        return (
            f"AcceptCall(call_id={self.getCallId()}, call_creator={self.getCallCreator()}, "
            f"audio={self.audioList}, net_medium={self.netMedium})"
        )

    # ── Accessors ──────────────────────────────────────────────

    def getCallKey(self) -> Optional[bytes]:
        return self.callKey

    def getAudioList(self) -> List[Dict[str, str]]:
        return self.audioList

    def getNetMedium(self) -> Optional[str]:
        return self.netMedium

    def getEncoptKeygen(self) -> Optional[str]:
        return self.encoptKeygen

    # ── Serialization ──────────────────────────────────────────

    def toProtocolTreeNode(self) -> ProtocolTreeNode:
        """
        Build <call><accept> stanza with E2E-encrypted callKey.

        The callKey is encrypted for the call-creator only using Signal Protocol.
        """
        node = super().toProtocolTreeNode()
        acceptNode = node.getChild("accept")

        children = [
            ProtocolTreeNode("audio", {"enc": "opus", "rate": "16000"}),
        ]

        # Add <te> ICE candidates (P2P)
        for te in self.te_candidates:
            children.append(ProtocolTreeNode("te", {"priority": str(te["priority"])}, data=te["data"]))

        children.append(ProtocolTreeNode("net", {"medium": self.netMedium}))
        children.append(ProtocolTreeNode("metadata", self.metaData))

        # Only add <enc> callKey if callKey is provided.
        # Real-device Frida capture: accept does NOT carry <enc> callKey —
        # the callKey was already exchanged in the offer (initiator generates,
        # callee decrypts). Accept only carries ICE candidates and capabilities.
        if self.callKey is not None and self.db is not None and self._callCreator is not None:
            call_key = self.callKey
            pb = e2e_pb2.Message()
            pb.call.call_key = call_key
            text = pb.SerializeToString()

            # Encrypt for the call-creator's device
            ciphertext = self.db.encrypt(self._callCreator, text)
            enc_type = "msg" if ciphertext.__class__ == WhisperMessage else "pkmsg"
            enc_data = ciphertext.serialize()
            enc_node = ProtocolTreeNode("enc", {"v": "2", "type": enc_type}, data=enc_data)
            children.append(enc_node)

        children.append(ProtocolTreeNode("encopt", {"keygen": self.encoptKeygen}))
        acceptNode.addChildren(children)
        return node

    # ── Deserialization ────────────────────────────────────────

    @staticmethod
    def fromProtocolTreeNode(node: ProtocolTreeNode, db: Any = None) -> "AcceptCallProtocolEntity":
        """
        Parse a <call> ProtocolTreeNode containing an <accept> child.

        Decrypts the callKey from the <enc> node using the provided
        axolotl_manager (db).
        """
        accept_node = node.getChild("accept")
        if accept_node is None:
            raise ValueError("Not an accept call: missing <accept> child")

        call_creator = accept_node.getAttributeValue("call-creator")
        call_id = accept_node.getAttributeValue("call-id")

        # <audio> × N
        audio_list = []
        for audio_node in accept_node.getAllChildren("audio"):
            rate = audio_node.getAttributeValue("rate")
            enc = audio_node.getAttributeValue("enc")
            if rate and enc:
                audio_list.append({"rate": rate, "enc": enc})

        # <net>
        net_medium = None
        net_node = accept_node.getChild("net")
        if net_node:
            net_medium = net_node.getAttributeValue("medium")

        # <encopt>
        encopt_keygen = None
        encopt_node = accept_node.getChild("encopt")
        if encopt_node:
            encopt_keygen = encopt_node.getAttributeValue("keygen")

        meta_data = None
        meta_node = accept_node.getChild("metadata")
        if meta_node:
            meta_data = {k: v for k, v in meta_node.attributes.items()}     


        # <enc> — decrypt callKey
        call_key = None
        enc_node = accept_node.getChild("enc")
        if enc_node and db is not None:
            enc_data = enc_node.getData()
            enc_type = enc_node.getAttributeValue("type")
            jid = node["from"]

            if enc_data and jid:
                try:
                    if enc_type == "msg":
                        text = db.decrypt_msg(jid, enc_data, True)
                    else:
                        text = db.decrypt_pkmsg(jid, enc_data, True)
                    e2e_msg = e2e_pb2.Message()
                    e2e_msg.ParseFromString(text)
                    call_key = e2e_msg.call.call_key
                except Exception:
                    # Decryption failed — may happen if session not established
                    pass

        return AcceptCallProtocolEntity(
            callId=call_id,
            callCreator=call_creator,
            callKey=call_key,
            audioList=audio_list,
            netMedium=net_medium,
            encoptKeygen=encopt_keygen,
            metaData=meta_data,
            callMetaAttributes=CallMetaAttributes.from_call_protocoltreenode(node),
            db=db,
        )
