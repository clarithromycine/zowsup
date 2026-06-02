from .....structs import  ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
from .....common import YowConstants
from proto import wa_struct_pb2
class MultiDevicePairCompanionHelloIqProtocolEntity(IqProtocolEntity):

    '''
    <iq id='07' xmlns='md' type='set' to='s.whatsapp.net'>
        <link_code_companion_reg jid="primary_jid" stage="companion_hello" should_show_push_notification="true">
            <link_code_pairing_wrapped_companion_ephemeral_pub>
            0x920351559a2239ee0af27d63f9e383e56a86c2a7be5c8d798c7385f3a1df9dca2a7a8ea9448319d0767069fdc32da163708d9ad88e132546be1c27de9c5320de5b9108e685d0f88ff34bf6d5c4b87a5a
            </link_code_pairing_wrapped_companion_ephemeral_pub>
            <link_code_pairing_nonce>
            0x00
            </link_code_pairing_nonce>
            <companion_server_auth_key_pub>
            0x9658c22318f60140a060e6933c87d29a0193bb177c780c3cfcc7762da605fc2e
            </companion_server_auth_key_pub>
            <companion_platform_id>
            0x31
            </companion_platform_id>
            <companion_platform_display>
            0x4368726f6d65202857696e646f777329
            </companion_platform_display>
        </link_code_companion_reg>
    </iq>
    '''

    def __init__(self,jid,shouldshowPushNotification,linkCodePairingWrappedCompanionEphemeralPub,companionServerAuthKeyPub,_id=None) -> None:
        super().__init__(_id = _id, _type = "set",to=YowConstants.DOMAIN, xmlns="md")
        self.stage = "companion_hello"
        self.jid = jid
        self.shouldshowPushNotification = shouldshowPushNotification
        self.linkCodePairingWrappedCompanionEphemeralPub = linkCodePairingWrappedCompanionEphemeralPub
        self.companionServerAuthKeyPub = companionServerAuthKeyPub                
        self.linkCodePairingNonce = b'\x00'
        self.companionPlatformId = b'\x31'
        self.companionPlatformDisplay = b"Chrome (Windows)"

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        linkCodeCompanionRegNode = ProtocolTreeNode("link_code_companion_reg",{"stage":self.stage,"should_show_push_notification":self.shouldshowPushNotification,"jid":self.jid})        

        linkCodePairingWrappedCompanionEphemeralPubNode = ProtocolTreeNode("link_code_pairing_wrapped_companion_ephemeral_pub", {}, None, self.linkCodePairingWrappedCompanionEphemeralPub)

        linkCodePairingNonceNode = ProtocolTreeNode("link_code_pairing_nonce", {}, None, self.linkCodePairingNonce)
        companionServerAuthKeyPubNode = ProtocolTreeNode("companion_server_auth_key_pub", {}, None, self.companionServerAuthKeyPub)
        companionPlatformIdNode = ProtocolTreeNode("companion_platform_id", {}, None, self.companionPlatformId)
        companionPlatformDisplayNode = ProtocolTreeNode("companion_platform_display", {}, None, self.companionPlatformDisplay)        
        linkCodeCompanionRegNode.addChild(linkCodePairingWrappedCompanionEphemeralPubNode)
        linkCodeCompanionRegNode.addChild(linkCodePairingNonceNode)
        linkCodeCompanionRegNode.addChild(companionServerAuthKeyPubNode)
        linkCodeCompanionRegNode.addChild(companionPlatformIdNode)
        linkCodeCompanionRegNode.addChild(companionPlatformDisplayNode)                                
        node.addChild(linkCodeCompanionRegNode)        
        return node

        


