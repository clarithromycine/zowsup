
from .....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
class SetPrivacyIqProtocolEntity(IqProtocolEntity):

    '''
    <iq to='s.whatsapp.net' type='set' id='01' xmlns='privacy'><privacy><category name='profile' value='contacts'/></privacy></iq>
    

    #以下这种blacklist复杂模式暂不实现，有用到再说吧
    <iq id='0f' to='s.whatsapp.net' xmlns='privacy' type='set'><privacy addressing_mode='lid'><category name='profile' value='contact_blacklist'><user action='add' pn_jid='6144@s.whatsapp.net' jid='1511@lid'/></category></privacy></iq>
    
    '''    
    def __init__(self, _id = None,name=None,value=None) -> None:
        super().__init__("privacy" , _id = _id, _type = "set",to="s.whatsapp.net")
        self.name = name
        self.value = value

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        nodePrivacy = ProtocolTreeNode("privacy",{})

        nodeCategory = ProtocolTreeNode("category",{"name":self.name,"value":self.value})
        nodePrivacy.addChild(nodeCategory)
        node.addChild(nodePrivacy)   
        return node    
    


