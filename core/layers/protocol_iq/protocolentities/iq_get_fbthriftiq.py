from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .iq import IqProtocolEntity
class GetFbThriftIqIqProtocolEntity(IqProtocolEntity):

    '''
        <iq to='s.whatsapp.net' type='get' id='094' xmlns='fb:thrift_iq'><request type='catkit' op='profile_typeahead' v='1'><query></query></request></iq>
        
        <iq xmlns='fb:thrift_iq' smax_id='118' to='s.whatsapp.net' type='get' from='639562902779@s.whatsapp.net' id='0c'/>

        <iq id='088' xmlns='fb:thrift_iq' type='get' smax_id='42' to='s.whatsapp.net'><linked_accounts/></iq>

        <iq xmlns='fb:thrift_iq' smax_id='104' to='s.whatsapp.net' type='get' from='8801319167529@s.whatsapp.net' id='031'><parameters><code>khp5MYVPIl9j8ENOiy3S4LFmrir18XeCyd1i6aLhY52ugepQHkyLoL8Sfb8YZNdK</code></parameters></iq>

    '''

    def __init__(self, smax_id=None, data={}, _id = None) -> None:
        super().__init__("fb:thrift_iq" , _id = _id, _type = "get",to="s.whatsapp.net",smax_id=smax_id)
        self.smax_id = smax_id
        self.data = data
                
    def toProtocolTreeNode(self) -> Any:        
        node = super().toProtocolTreeNode()

        if self.smax_id is None:
            request = ProtocolTreeNode("request",{"type":"catkit","op":"profile_typeahead","v":"1"})
            query = ProtocolTreeNode("query")
            request.addChild(query)
            node.addChild(request)

        if self.smax_id == "118":
            pass

        if self.smax_id == "42":
            linked_accounts = ProtocolTreeNode("linked_accounts")
            node.addChild(linked_accounts)

        if self.smax_id=="104":
            parametersNode = ProtocolTreeNode("parameters")
            codeNode = ProtocolTreeNode("code")
            codeNode.setData(self.data["nonce"])
            parametersNode.addChild(codeNode)
            node.addChild(parametersNode)

        return node    
