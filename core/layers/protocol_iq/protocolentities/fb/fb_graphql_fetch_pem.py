from .....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
from .....common import YowConstants
import time

class FbGraphqlFetchPem(IqProtocolEntity):

    '''
    <iq smax_id='18' id='04' xmlns='fb:graphql' type='get' to='s.whatsapp.net'>
        <supported_certificates>rsa2048</supported_certificates>
        <fetch_password_pem>true</fetch_password_pem>
        <auth_metadata timestamp='1784276180' version='1' use_case='support'/>
    </iq>
    '''

    def __init__(self,  timestamp=None, use_case="support") -> None:
        super().__init__(xmlns="fb:graphql", _type="get", to=YowConstants.DOMAIN, smax_id='18')
        self.timestamp = timestamp or int(time.time())
        self.use_case = use_case

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()

        sc_node = ProtocolTreeNode("supported_certificates", {}, None, b"rsa2048")
        node.addChild(sc_node)

        fpp_node = ProtocolTreeNode("fetch_password_pem", {}, None, b"true")
        node.addChild(fpp_node)

        am_node = ProtocolTreeNode("auth_metadata", {
            "timestamp": str(self.timestamp),
            "version": "1",
            "use_case": self.use_case
        })
        node.addChild(am_node)

        return node

        

class ResultFbGraphqlFetchPemIqProtocolEntity(IqProtocolEntity):

    '''
    <iq from='s.whatsapp.net' type='result' id='04'>
        <reply algorithm='rsa2048' version='1'>
            <encryption_pem>-----BEGIN CERTIFICATE-----...-----END CERTIFICATE-----</encryption_pem>
            <signature_pem>-----BEGIN CERTIFICATE-----...-----END CERTIFICATE-----</signature_pem>
            <password_pem key_id='47' ttl='199306'>-----BEGIN PUBLIC KEY-----...-----END PUBLIC KEY-----</password_pem>
        </reply>
    </iq>
    '''

    def __init__(self, algorithm="rsa2048", version="1",
                 encryption_pem=None, signature_pem=None,
                 password_pem=None, password_pem_key_id=None, password_pem_ttl=None) -> None:
        super().__init__()
        self.algorithm = algorithm
        self.version = version
        self.encryption_pem = encryption_pem
        self.signature_pem = signature_pem
        self.password_pem = password_pem
        self.password_pem_key_id = password_pem_key_id
        self.password_pem_ttl = password_pem_ttl

    @staticmethod
    def fromProtocolTreeNode(node):

        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = ResultFbGraphqlFetchPemIqProtocolEntity

        reply_node = node.getChild("reply")
        if reply_node is None:
            return None

        entity.algorithm = reply_node.getAttributeValue("algorithm") or "rsa2048"
        entity.version = reply_node.getAttributeValue("version") or "1"


        enc_node = reply_node.getChild("encryption_pem")
        if enc_node and enc_node.data:
            entity.encryption_pem = enc_node.data.decode("utf-8")

        sig_node = reply_node.getChild("signature_pem")
        if sig_node and sig_node.data:
            entity.signature_pem = sig_node.data.decode("utf-8")

        pwd_node = reply_node.getChild("password_pem")
        if pwd_node:
            if pwd_node.data:
                entity.password_pem = pwd_node.data.decode("utf-8")
            entity.password_pem_key_id = pwd_node.getAttributeValue("key_id")
            entity.password_pem_ttl = pwd_node.getAttributeValue("ttl")
        
        return entity