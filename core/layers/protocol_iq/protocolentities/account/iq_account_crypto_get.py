from ..iq import IqProtocolEntity
from typing import Optional, Any, List, Dict, Union
from .....structs import ProtocolTreeNode

class CryptoGetIqProtocolEntity(IqProtocolEntity):

    '''
        <iq to='s.whatsapp.net' xmlns='urn:xmpp:whatsapp:account' type='get' id='013'>
            <crypto action='get' version="{VERSION}“>
                <google>......</google>
                <code>......</google>
            </crypto>
        </iq>
    '''

    def __init__(self,version=None,data=None,code=None) -> None:
        super().__init__("urn:xmpp:whatsapp:account", _type="get")
        self.version = version    
        self.data = data   
        self.code = code     

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        cryptoNode = ProtocolTreeNode("crypto", {"action": "get","version":self.version})
        googleNode = ProtocolTreeNode("google", data =self.data)
        codeNode = ProtocolTreeNode("code", data =self.code)
        cryptoNode.addChild(googleNode)
        cryptoNode.addChild(codeNode)        
        node.addChild(cryptoNode)
        return node