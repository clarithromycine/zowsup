from .....structs import  ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
from .....common import YowConstants
from proto import wa_struct_pb2
class MultiDevicePairSignIqProtocolEntity(IqProtocolEntity):

    '''

    <iq to='s.whatsapp.net' type='result' id='3669502021'>
        <pair-device-sign>
            <device-identity key-index='4'>
                Cg4Iqe+U4wEQrNfFoAYYBBpAD+AftGhw5/gBuHifYsi4W7PcIv4l6wmfZn6r5t7i+woV/yttQeSb7AtOayxK3QxUXGvaW5cLWIRM3NpFyDQXCyJA8nyAbXObfni+L7pDVjiFSdVNXNHJyjNoDwBWPxK/U9uOf2Qa5IrMLuzyEIqbtwFFkwvRi8VIZli8pdZECIYqAw==
            </device-identity>
        </pair-device-sign>
    </iq>
    '''

    def __init__(self,_id,keyIndex,sign) -> None:
        super().__init__(_id = _id, _type = "result",to=YowConstants.DOMAIN)
        self.keyIndex = keyIndex
        self.sign = sign        

    def setKeyIndex(self, value) -> Any:
        self.keyIndex = value

    def setSignature(self, value) -> Any:
        self.sign = value

    def __str__(self):
        out = super().__str__()
        out += "key-index: %s\n" % self.keyIndex
        out += "signature: %s\n" % self.sign        
        return out

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        deviceEntityNode = ProtocolTreeNode("device-identity", {"key-index": str(self.keyIndex)}, None, self.sign)
        pairDeviceSignNode = ProtocolTreeNode("pair-device-sign",{})
        pairDeviceSignNode.addChild(deviceEntityNode)
        node.addChild(pairDeviceSignNode)        
        return node

        


