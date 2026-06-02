from .....structs import  ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
from .....common import YowConstants
from proto import wa_struct_pb2
class MultiDevicePairSuccessIqProtocolEntity(IqProtocolEntity):

    '''

    <iq from="s.whatsapp.net" type="set" id="3979800857" xmlns="md">
        <pair-success>
            <platform name="android" />
            <device-identity>
                0x0a740a0e0884f292f60210bfbfeea0061801122073eae4ded0815d0b61ac4c07ee08b470da7097f62278a35fc3347b2f8e431a2b1a40cb3c99c995db6a7bc3df9912ea42c03802925a512588ebf7948f76df48400fee1c26820fdb40b433126817bc68ee0f2e49791df955075d7c5c5ac6f3ed5ebe0d122020a9a3e7902bc072919654138c072c1e3f7b7f5ad1f126ab80b09bb2aa95631e
            </device-identity>
            <device jid="8619874406144.0:19@s.whatsapp.net" />
        </pair-success>
    </iq>  
    '''

    def __init__(self,_id) -> None:
        super().__init__(_id = _id, _type = "set", _from = YowConstants.DOMAIN, xmlns="md")
        self.platform = None
        self.device_identity = None
        self.jid=None

    def setRefs(self, refs) -> Any:
        self.refs = refs

    def __str__(self):
        out = super().__str__()
        out += "platform: %s\n" % self.platform
        out += "device-identity: %s\n" % self.device_identity
        out += "jid: %s\n" % self.jid
        return out

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = MultiDevicePairSuccessIqProtocolEntity
        nodePairSuccess = node.getChild("pair-success")        
        if nodePairSuccess is not None:            
            entity.platform = nodePairSuccess.getChild("platform").getAttributeValue("name")
            entity.device_identity = nodePairSuccess.getChild("device-identity").getData()
            entity.jid = nodePairSuccess.getChild("device").getAttributeValue("jid")        
            return entity
        else:            
            return None
        


