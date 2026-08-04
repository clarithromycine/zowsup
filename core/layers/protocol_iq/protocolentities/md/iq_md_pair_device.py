from .....structs import  ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
from .....common import YowConstants
from proto import wa_struct_pb2
import time

#这个请求时主设备发起的  (v0.11+: 新增 pem / encryption-metadata / client-props / challenges)

class MultiDevicePairDeviceIqProtocolEntity(IqProtocolEntity):

    '''
    <iq to='s.whatsapp.net' id='09' xmlns='md' type='set'>
        <pair-device>
            <ref>...</ref>
            <pub-key>...</pub-key>
            <device-identity>...</device-identity>
            <key-index-list ts='1723179936'>...</key-index-list>

            <!-- v0.11+ new fields -->
            <client-props>...</client-props>
            <pem version='1' algorithm='rsa2048'>
                <pem>{secretKey base64}</pem>
                <ttl ts_s='432000'/>
                <key_id>1</key_id>
            </pem>
            <encryption-metadata version='1' algorithm='rsa2048'>
                <encrypted_key>{base64}</encrypted_key>
                <nonce>{base64}</nonce>
                <encrypted_data>{base64}</encrypted_data>
                <auth_tag>{base64}</auth_tag>
            </encryption-metadata>
            <challenges>
                <supported>
                    <friction variant='1'/>
                </supported>
            </challenges>
        </pair-device>
    </iq>

    '''

    def __init__(
        self,
        ref,
        pubKey,
        deviceIdentity,
        keyIndexList,
        _id=None,
        # v0.11+ new fields (optional, None = old protocol)
        clientProps: Optional[bytes] = None,
        secretKey: Optional[bytes] = None,           # 32-byte derived key for <pem>
        encryptionMetadata: Optional[dict] = None,    # {encrypted_key, nonce, encrypted_data, auth_tag}
        challenges: Optional[List[ProtocolTreeNode]] = None,
        companionQrOriginSource: Optional[str] = None,  # "1" or "2"
        keyIndexTs: Optional[int] = None,
        certKeyId: Optional[int] = None,  # key_id from WWWGetCertificates
    ) -> None:
        super().__init__(_id = _id, _type = "set", to=YowConstants.DOMAIN, xmlns="md")
        self.ref = ref
        self.pubKey = pubKey
        self.deviceIdentity = deviceIdentity
        self.keyIndexList = keyIndexList
        self.clientProps = clientProps
        self.secretKey = secretKey
        self.encryptionMetadata = encryptionMetadata
        self.challenges = challenges or []
        self.companionQrOriginSource = companionQrOriginSource
        self.keyIndexTs = keyIndexTs
        self.certKeyId = certKeyId

    def toProtocolTreeNode(self) -> Any:

        node = super().toProtocolTreeNode()
        pairDeviceNode = ProtocolTreeNode("pair-device", {})

        ref = ProtocolTreeNode("ref", {}, None, self.ref)
        pubKey = ProtocolTreeNode("pub-key", {}, None, self.pubKey)
        deviceIdentity = ProtocolTreeNode("device-identity", {}, None, self.deviceIdentity)
        ts = str(self.keyIndexTs if self.keyIndexTs is not None else int(time.time()))
        keyIndexList = ProtocolTreeNode("key-index-list", {"ts": ts}, None, self.keyIndexList)

        pairDeviceNode.addChild(ref)
        pairDeviceNode.addChild(pubKey)
        pairDeviceNode.addChild(deviceIdentity)
        pairDeviceNode.addChild(keyIndexList)

        # v0.11+ client-props
        if self.clientProps is not None:
            pairDeviceNode.addChild(ProtocolTreeNode("client-props", {}, None, self.clientProps))

        # v0.11+ companion_qr_origin_source
        if self.companionQrOriginSource is not None:
            pairDeviceNode.addChild(ProtocolTreeNode(
                "companion_qr_origin_source", {}, None, self.companionQrOriginSource.encode()
            ))

        # v0.11+ pem (derived secretKey)
        if self.secretKey is not None:
            pemNode = ProtocolTreeNode("pem", {"version": "1", "algorithm": "rsa2048"})
            pemNode.addChild(ProtocolTreeNode("pem", {}, None, self.secretKey))
            pemNode.addChild(ProtocolTreeNode("ttl", {"ts_s": "432000"}, None, None))
            key_id_bytes = str(self.certKeyId if self.certKeyId is not None else 1).encode()
            pemNode.addChild(ProtocolTreeNode("key_id", {}, None, key_id_bytes))
            pairDeviceNode.addChild(pemNode)

        # v0.11+ encryption-metadata
        if self.encryptionMetadata is not None:
            encNode = ProtocolTreeNode("encryption-metadata", {"version": "1", "algorithm": "rsa2048"})
            encNode.addChild(ProtocolTreeNode("encrypted_key", {}, None,
                self.encryptionMetadata["encrypted_key"]))
            encNode.addChild(ProtocolTreeNode("nonce", {}, None,
                self.encryptionMetadata["nonce"]))
            encNode.addChild(ProtocolTreeNode("encrypted_data", {}, None,
                self.encryptionMetadata["encrypted_data"]))
            encNode.addChild(ProtocolTreeNode("auth_tag", {}, None,
                self.encryptionMetadata["auth_tag"]))
            pairDeviceNode.addChild(encNode)

        # v0.11+ challenges
        if self.challenges:
            challengesNode = ProtocolTreeNode("challenges", {}, None, None)
            for child in self.challenges:
                challengesNode.addChild(child)
            pairDeviceNode.addChild(challengesNode)

        node.addChild(pairDeviceNode)

        return node

        


