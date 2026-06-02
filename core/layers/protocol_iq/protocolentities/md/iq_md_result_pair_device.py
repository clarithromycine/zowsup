from .....structs import  ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
from .....common import YowConstants
from proto import wa_struct_pb2
import time


class MultiDevicePairDeviceResultIqProtocolEntity(IqProtocolEntity):

    '''
        <iq from="s.whatsapp.net" type="result" id="8XOCAM3QPBZN0VFH27S6YJUEL5K4WRDI">
        <companion-props>
            0x0a0757696e646f77731202080a180120002a1018efd908200138014001500158016001
        </companion-props>
        <device jid="212719800440.0:9@s.whatsapp.net" />
        </iq>

    '''

    def __init__(self,_id=None) -> None:
        super().__init__(_id = _id, _type = "result",to=YowConstants.DOMAIN, xmlns="md")
        self.companionProps = None
        self.deviceJid = None

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = MultiDevicePairDeviceResultIqProtocolEntity

        companionPropsNode = node.getChild("companion-props")         #以出现这个字段为正确返回
        if companionPropsNode is not None:      
            entity.companionProps = companionPropsNode.getData()
            entity.deviceJid = node.getChild("device").getAttributeValue("jid")
            return entity
        else:
            return None        



        


