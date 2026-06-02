from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .notification import NotificationProtocolEntity

class LinkCodeCompanionRegNotificationProtocolEntity(NotificationProtocolEntity):
    '''        
        stage = companion_hello

        <notification from="s.whatsapp.net" type="link_code_companion_reg" id="2519540305" t="1744768688">
        <link_code_companion_reg stage="companion_hello" should_show_push_notification="true">
            <link_code_pairing_wrapped_companion_ephemeral_pub>
            0xf904795088004d6fe2f8df4a88d0f8f4825dce1c0beb37fae04b5cacc3a250dae8edb07ac2400a3342dde8e30f6f0d5a7f42ace9698a2fbd391b09aca36b59576adc95919b6e5352e9a22f5631cdc984
            </link_code_pairing_wrapped_companion_ephemeral_pub>
            <link_code_pairing_nonce>
            0x00
            </link_code_pairing_nonce>
            <companion_server_auth_key_pub>
            0xa093cb525f00fc62b27cd344bcd1de046fffd87eabf7a1fe739d70359630743a
            </companion_server_auth_key_pub>
            <companion_platform_id>
            0x31
            </companion_platform_id>
            <companion_platform_display>
            0x4368726f6d65202857696e646f777329
            </companion_platform_display>
            <link_code_pairing_ref>
            0x3340323a494a6d4b4e464462234a4f6273427a4a5462786865476157672f544e64706378575a6773683578442b55765a31574c4e33475a374373556c445937537757645470594866436c5a356d6662557158567749484453644234784166712b486533354d4259384d51556b30364c453d
            </link_code_pairing_ref>
        </link_code_companion_reg>
        </notification>        

        stage = companion_finish

        <notification from="s.whatsapp.net" type="link_code_companion_reg" id="2330712893" t="1723190864">
            <link_code_companion_reg stage="companion_finish">
                <link_code_pairing_wrapped_key_bundle>
                0x452c1034bf6d4857d77a22ec4bfa5d39d8c011b7ad10d2b691644e3390ed9de7f228bf26a6c577e65f74ba8ae1c00c8d07db231a0de303a5575c00c30c1d25db6534785fda6447878f78bdfacb6c1078abf7f7a2b3a97ac95217d518ae3f8bebdfa2d78aed4c315a007150847ee1d1b4a053314e4753fb08c50a06f0a950e2794718b5ae6d5e559fec6ac1536c1d1f604cd754a33d0e925897669316
                </link_code_pairing_wrapped_key_bundle>
                <companion_identity_public>
                0xa5c0fdecff058542a6f19c67fb64680585c7b482de973c95dcde5382b68edc13
                </companion_identity_public>
                <link_code_pairing_ref>
                0x3340323a6d32317256794d44236a74303749384c2f64314f416a6d5858303955654d58663768304935414645723964725a785236576479424a6630504e5933464969776f786c2b546f414d70484b2b3134684765444f772b64387865357766665834387975777651316564765a6a6a4d3d
                </link_code_pairing_ref>
            </link_code_companion_reg>
        </notification>        

        stage = primary_hello
        
        <notification from="s.whatsapp.net" type="link_code_companion_reg" id="3357813253" t="1744861223">
        <link_code_companion_reg stage="primary_hello">
            <link_code_pairing_wrapped_primary_ephemeral_pub>
            0xb9434fc57d1573407f6ea9e8802f11a0b3ea8124e87d78fac567657239431afb712821760707fe61ab891dfa2dfaf17a1ff30a9d848dcca922379f12810aec76181b134dd0741bbb3519e7de7b07dc82
            </link_code_pairing_wrapped_primary_ephemeral_pub>
            <primary_identity_pub>
            0x6ea877518849578a66c008c3c02e84a6a6d812fa25bc795a5d1d8f12f39fba08
            </primary_identity_pub>
            <link_code_pairing_ref>
            0x3340323a386434736c44762f23652f50774d47704632546850655056326f5444506f743759756a74765a43583069673471724162534f3479544d6331597a4a484448543073306d797a66317a3654397250357962444755632f656a4c774f5172453035454b69714947382b50656a75453d
            </link_code_pairing_ref>
        </link_code_companion_reg>
        </notification>        

    '''

    def __init__(self, _id,  _from, stage, timestamp, notify, offline) -> None:
        super().__init__(_id, _from, timestamp, notify, offline)
        self.stage = stage

        #for companion_hello
        self.shouldShowPushNotification = None
        self.linkCodePairingWrappedCompanionEphemeralPub = None
        self.linkCodePairingNonce = None
        self.companionServerAuthKeyPub = None
        self.companionPlatformId = None
        self.companionPlatformDisplay = None
        
        #for companion_finish
        self.linkCodePairingWrappedKeyBundle = None
        self.companionIdentityPublic = None

        #for primary_hello
        self.linkCodePairingWrappedPrimaryEphemeralPub = None
        self.primaryIdentityPublic = None

        #for all
        self.linkCodePairingRef = None


    @staticmethod
    def fromProtocolTreeNode(node):
        entity = NotificationProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = LinkCodeCompanionRegNotificationProtocolEntity
        node = node.getChild("link_code_companion_reg")
        entity.stage = node.getAttributeValue("stage")                
        
        #for companion_hello
        entity.shouldShowPushNotification=node.getAttributeValue("should_show_push_notification") if node.getAttributeValue("should_show_push_notification") is not None else None
        entity.linkCodePairingWrappedCompanionEphemeralPub = node.getChild("link_code_pairing_wrapped_companion_ephemeral_pub").getData() if node.getChild("link_code_pairing_wrapped_companion_ephemeral_pub") is not None else None
        
        entity.linkCodePairingNonce = node.getChild("link_code_pairing_nonce").getData() if node.getChild("link_code_pairing_nonce") is not None else None
        entity.companionServerAuthKeyPub = node.getChild("companion_server_auth_key_pub").getData() if node.getChild("companion_server_auth_key_pub") is not None else None
        entity.companionPlatformId = node.getChild("companion_platform_id").getData() if node.getChild("companion_platform_id") is not None else None
        entity.companionPlatformDisplay = node.getChild("companion_platform_display").getData() if node.getChild("companion_platform_display") is not None else None

        #for companion_finish
        entity.linkCodePairingWrappedKeyBundle = node.getChild("link_code_pairing_wrapped_key_bundle").getData() if node.getChild("link_code_pairing_wrapped_key_bundle") is not None else None
        entity.companionIdentityPublic = node.getChild("companion_identity_public").getData() if node.getChild("companion_identity_public") is not None else None

        #for primay_hello
        entity.linkCodePairingWrappedPrimaryEphemeralPub = node.getChild("link_code_pairing_wrapped_primary_ephemeral_pub").getData() if node.getChild("link_code_pairing_wrapped_primary_ephemeral_pub") is not None else None
        entity.primaryIdentityPublic = node.getChild("primary_identity_pub").getData() if node.getChild("primary_identity_pub") is not None else None


        #for all
        entity.linkCodePairingRef = node.getChild("link_code_pairing_ref").getData() if node.getChild("link_code_pairing_ref") is not None else None


        return entity