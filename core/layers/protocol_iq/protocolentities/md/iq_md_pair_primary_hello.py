from .....structs import  ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
from .....common import YowConstants
from proto import wa_struct_pb2
class MultiDevicePairPrimaryHelloIqProtocolEntity(IqProtocolEntity):

    '''
    <iq id='07' xmlns='md' type='set' to='s.whatsapp.net'>
        <link_code_companion_reg stage='primary_hello'>
            <link_code_pairing_wrapped_primary_ephemeral_pub>
                /7uot+V6g/umhqTh7WGi4Tjn5jPi9AYeuG0fmw1/zDN0MQrmouTuox91uq8uu4ouoc2TM0YZeJ/gKATZIKOPt6FomfetxtAZCdsWfP3QWuI=
            </link_code_pairing_wrapped_primary_ephemeral_pub>
            <primary_identity_pub>
                RCKB1ACJA3wyhffwPwsihNzrXC8NSQmxJ1ctsmhYhl4=
            </primary_identity_pub>
            <link_code_pairing_ref>
                3@2:DihbmHhw#CNtKoTVp8481ohQwWbbV6YZ1jse0rEBWxB8Myt/LT8ex7dJlOe/BiIigDS6f+mNTfXPYcLtOLp8CDe0pk6P+HKr764Rnno3IYTY=
            </link_code_pairing_ref>
        </link_code_companion_reg>
    </iq>
    '''

    def __init__(self,linkCodePairingWrappedPrimaryEphemeralPub,primaryIdentityPub,linkCodePairingRef,_id=None) -> None:
        super().__init__(_id = _id, _type = "set",to=YowConstants.DOMAIN, xmlns="md")
        self.stage = "primary_hello"
        self.linkCodePairingWrappedPrimaryEphemeralPub = linkCodePairingWrappedPrimaryEphemeralPub
        self.primaryIdentityPub = primaryIdentityPub        
        self.linkCodePairingRef = linkCodePairingRef


    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        linkCodeCompanionRegNode = ProtocolTreeNode("link_code_companion_reg",{"stage":self.stage})        
        linkCodePairingWrappedPrimaryEphemeralPubNode = ProtocolTreeNode("link_code_pairing_wrapped_primary_ephemeral_pub", {}, None, self.linkCodePairingWrappedPrimaryEphemeralPub)
        primaryIdentityPub = ProtocolTreeNode("primary_identity_pub", {}, None, self.primaryIdentityPub)
        linkCodePairingRef = ProtocolTreeNode("link_code_pairing_ref", {}, None, self.linkCodePairingRef)
        linkCodeCompanionRegNode.addChild(linkCodePairingWrappedPrimaryEphemeralPubNode)
        linkCodeCompanionRegNode.addChild(primaryIdentityPub)
        linkCodeCompanionRegNode.addChild(linkCodePairingRef)
        node.addChild(linkCodeCompanionRegNode)        
        return node

        


