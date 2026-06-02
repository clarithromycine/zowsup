from ..iq import IqProtocolEntity
from typing import Optional, Any, List, Dict, Union
from .....structs import ProtocolTreeNode
import codecs
class CryptoCreateIqProtocolEntity(IqProtocolEntity):

    '''
        <iq to='s.whatsapp.net' xmlns='urn:xmpp:whatsapp:account' type='get' id='013'>
            <crypto action='create'>
                <google>fg3UG5/eUPeqfRv1Ge2RbcJWj05rbtAnvOXqY1vtSxQ=</google>
            </crypto>
        </iq>
    '''

    def __init__(self,data=None) -> None:
        super().__init__("urn:xmpp:whatsapp:account", _type="get")
        if data is None:
            #demo
            data = codecs.decode("fe5cf90c511fb899781bbed754577098e460d048312c8b36c11c91ca4b49ca34", 'hex')            
        self.data = data        


    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        cryptoNode = ProtocolTreeNode("crypto", {"action": "create"})
        googleNode = ProtocolTreeNode("google", data =self.data)
        cryptoNode.addChild(googleNode)
        node.addChild(cryptoNode)
        return node