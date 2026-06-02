from .....structs import  ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
from .....common import YowConstants
class MultiDevicePairCompanionFinishIqProtocolEntity(IqProtocolEntity):

    '''
    <iq id='07' xmlns='md' type='set' to='s.whatsapp.net'>
        <link_code_companion_reg jid="primary_jid" stage="companion_finish" >
            <link_code_pairing_wrapped_key_bundle>
            ...
            </link_code_pairing_wrapped_key_bundle>
            <companion_identity_public>
            ...
            </companion_identity_public>
            <link_code_pairing_ref>
            ...
            </link_code_pairing_ref>

        </link_code_companion_reg>
    </iq>
    '''

    def __init__(self,jid,linkCodePairingWrappedKeyBundle,companionIdentityPublic,linkCodePairingRef,_id=None) -> None:
        super().__init__(_id = _id, _type = "set",to=YowConstants.DOMAIN, xmlns="md")
        self.stage = "companion_finish"
        self.jid = jid
        self.linkCodePairingWrappedKeyBundle = linkCodePairingWrappedKeyBundle
        self.companionIdentityPublic = companionIdentityPublic
        self.linkCodePairingRef = linkCodePairingRef

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        linkCodeCompanionRegNode = ProtocolTreeNode("link_code_companion_reg",{"stage":self.stage,"jid":self.jid})        
        linkCodePairingWrappedKeyBundle = ProtocolTreeNode("link_code_pairing_wrapped_key_bundle", {}, None, self.linkCodePairingWrappedKeyBundle)
        companionIdentityPublic = ProtocolTreeNode("companion_identity_public", {}, None, self.companionIdentityPublic)
        linkCodePairingRef = ProtocolTreeNode("link_code_pairing_ref", {}, None, self.linkCodePairingRef)        
        linkCodeCompanionRegNode.addChild(linkCodePairingWrappedKeyBundle)
        linkCodeCompanionRegNode.addChild(companionIdentityPublic)
        linkCodeCompanionRegNode.addChild(linkCodePairingRef)        
        node.addChild(linkCodeCompanionRegNode)        
        return node

        


