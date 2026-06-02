from .....structs import  ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
from .....common import YowConstants
from proto import wa_struct_pb2
import time



#这个请求时主设备发起的

class MultiDevicePairDeviceIqProtocolEntity(IqProtocolEntity):

    '''
    <iq to='s.whatsapp.net' id='09' xmlns='md' type='set'>
        <pair-device>
            <ref>
                3@2:yl4ZOM27#E8N7mdy9LgbZPdLXUVu7+fC/lPgMfNoXXuMWeOUH5UgRCT/zyCfRBnG9EezdJk6IQSAKB3LVp7lxDd8bZxZSYxnEFxuW3keYxvE=
            </ref>
            <pub-key>
                fzhoDjfvz+FpEtCUkb2GgTbbO/WGzS+V4arpSGRGwEU=
            </pub-key>
            <device-identity>
                CngKEgjboJW1BRCgx9a1BhgBIAAoABIghkQhTSDEX+X4EwtfYAa6Y8idcQpf/xbtKk0CPah94UgaQAZonDDV+RqBweoG9yYg1QFqCfgb5edUJhOQuH6f+FIOBIe0APom25y7XNhmzt7sJI5PiJ0DXTye3xn3yHyXDQsSIOc6wehKoJ0QAlEsm4qQCaIC+DGgUHjjSaZx6zbSZZlLGAA=
            </device-identity>
            <key-index-list ts='1723179936'>
                ChQI26CVtQUQoMfWtQYYASICAAEoABJAtAGpyimmDqTYrlkJeFRig843ZAz54wz1Srths/QI5BGQBY8TQni6dWIcFKhFnqU/UhZpM1vtdemhkr3gvD1EBQ==
            </key-index-list>
        </pair-device>
    </iq>

    '''

    def __init__(self,ref,pubKey,deviceIdentity,keyIndexList,_id=None) -> None:
        super().__init__(_id = _id, _type = "set",to=YowConstants.DOMAIN, xmlns="md")
        self.ref = ref
        self.pubKey = pubKey        
        self.deviceIdentity = deviceIdentity
        self.keyIndexList = keyIndexList

    def toProtocolTreeNode(self) -> Any:

        node = super().toProtocolTreeNode()
        pairDeviceNode = ProtocolTreeNode("pair-device",{})        

        ref = ProtocolTreeNode("ref", {}, None, self.ref)
        pubKey = ProtocolTreeNode("pub-key", {}, None, self.pubKey)
        deviceIdentity = ProtocolTreeNode("device-identity", {}, None, self.deviceIdentity)
        keyIndexList = ProtocolTreeNode("key-index-list", {"ts":str(int(time.time()))}, None, self.keyIndexList)

        pairDeviceNode.addChild(ref)        
        pairDeviceNode.addChild(pubKey)        
        pairDeviceNode.addChild(deviceIdentity)        
        pairDeviceNode.addChild(keyIndexList)        
        node.addChild(pairDeviceNode)        

        return node

        


