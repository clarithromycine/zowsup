
from .....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
class GetPrivacyIqProtocolEntity(IqProtocolEntity):



    '''
    发：<iq to='s.whatsapp.net' id='05' xmlns='privacy' type='get'><privacy/></iq>        
    '''    
    def __init__(self, _id = None) -> None:
        super().__init__("privacy" , _id = _id, _type = "get",to="s.whatsapp.net")

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        nodePrivacy = ProtocolTreeNode("privacy",{})
        node.addChild(nodePrivacy)   
        return node    
    


class ResultPrivacyIqProtocolEntity(IqProtocolEntity):

    '''
    <iq from='s.whatsapp.net' type='result' id='07'>
      <privacy>
        <category name='calladd' value='all'/>
        <category name='cover_photo' value='all'/>
        <category name='defense' value='off'/>
        <category name='dependentaccountmessages' value='all'/>
        <category name='groupadd' value='all'/>
        <category name='groupcreation' value='on_standard'/>
        <category name='linked_profiles' value='contacts'/>
        <category name='messages' value='all'/>
        <category name='online' value='all'/>
        <category name='last' value='contacts'/>
        <category name='profile' value='contact_blacklist' dhash='1784013941534'/>
        <category name='readreceipts' value='all'/>
        <category name='status' value='contacts'/>
        <category name='stickers' value='contacts'/>
      </privacy>
    </iq>        
    '''
    def __init__(self, _id = None, setting = {}) -> None:
        super().__init__("privacy" , _id = _id, _type = "result",to="s.whatsapp.net")
        self.setting = setting

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        nodePrivacy = ProtocolTreeNode("privacy",{})
        node.addChild(nodePrivacy)   
        return node
    
    @staticmethod
    def fromProtocolTreeNode(node) :
        setting = {}
        if node is not None and node.getChild("privacy") is not None:
            privacyNode = node.getChild("privacy")
            setting = {}
            for child in privacyNode.getAllChildren():
                #暂不处理contact_blacklist这种复杂模式，先处理简单的
                setting[child.getAttributeValue("name")] =  child.getAttributeValue("value")

        return ResultPrivacyIqProtocolEntity(_id=node["id"], setting=setting)

