from ....common import YowConstants
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_iq.protocolentities import IqProtocolEntity
from ....structs import ProtocolTreeNode
from ....layers.protocol_iq.protocolentities import ResultIqProtocolEntity


class GetKeysCountIqProtocolEntity(IqProtocolEntity):
    def __init__(self) -> None:
        super().__init__("encrypt", _type="get", to=YowConstants.WHATSAPP_SERVER)

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        countNode = ProtocolTreeNode("count")
        node.addChild(countNode)
        return node

class ResultKeyCountIqProtocolEntity(ResultIqProtocolEntity):

    '''
    <iq from="s.whatsapp.net" type="result" id="3979800857">
        <count value="812" />
    </iq>  
    '''

    def __init__(self,_id,count) -> None:
        super().__init__(_id = _id, _type = "result", _from = YowConstants.DOMAIN)
        self.count = int(count)


    def __str__(self):
        out = super().__str__()
        out += "count: %d\n" % self.count
        return out

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = ResultIqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = ResultKeyCountIqProtocolEntity
        result = node.getChild("count")                
        if result is not None:      
            value = result.getAttributeValue("value")
            entity.count = int(value)
            return entity
        else:            
            return None
