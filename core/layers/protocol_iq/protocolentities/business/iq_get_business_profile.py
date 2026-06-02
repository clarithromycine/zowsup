from .....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
class GetBusinessProfileIqProtocolEntity(IqProtocolEntity):

    '''
        <iq id='025' xmlns='w:biz' type='get'>
            <business_profile v='1908'>
                <profile jid='8801319167529@s.whatsapp.net'/>
                <settings/>
                <server_configs/>
            </business_profile>
        </iq>
    '''

    def __init__(self, jid, _id = None) -> None:
        super().__init__("w:biz" , _id = _id, _type = "get",to="s.whatsapp.net")
        self.jid = jid
                
    def toProtocolTreeNode(self) -> Any:        
        node = super().toProtocolTreeNode()

        business_profile = ProtocolTreeNode("business_profile",{"v":"1908"})      
        setting =  ProtocolTreeNode("settings",{})
        server_configs =  ProtocolTreeNode("server_configs",{})
        business_profile.addChild(ProtocolTreeNode("profile",{"jid":self.jid}))     
        business_profile.addChild(setting)
        business_profile.addChild(server_configs)            
        node.addChild(business_profile)

        return node