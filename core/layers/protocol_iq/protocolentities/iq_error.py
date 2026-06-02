from ....structs import  ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .iq import IqProtocolEntity
class ErrorIqProtocolEntity(IqProtocolEntity):

    '''
    <iq id="1417113419-0" from="{{jid}}" type="error">
        <error text="not-acceptable" code="406" backoff="3600">
    </error>
    </iq>
    '''

    def __init__(self, _id, _from, code, text, backoff= 0 ) -> None:
        super().__init__(xmlns = None, _id = _id, _type = "error", _from = _from)
        self.setErrorProps(code, text, backoff)

    def setErrorProps(self, code, text, backoff) -> Any:
        self.code = code
        self.text = text
        self.backoff = int(backoff) if backoff else 0

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        errorNode = ProtocolTreeNode("error", {"text": self.text, "code": self.code})
        if self.backoff:
            errorNode.setAttribute("backoff", str(self.backoff))
        node.addChild(errorNode)
        return node

    def __str__(self):
        out = super().__str__()
        out += "Code: %s\n" % self.code
        out += "Text: %s\n" % self.text
        out += "Backoff: %s\n" % self.backoff
        return out

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = ErrorIqProtocolEntity
        errorNode = node.getChild("error")
        entity.setErrorProps(errorNode.getAttributeValue("code"),
                             errorNode.getAttributeValue("text"),
                             errorNode.getAttributeValue("backoff"))
        return entity


