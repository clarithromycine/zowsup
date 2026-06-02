from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union

class AckProtocolEntity(ProtocolEntity):

    '''
    <ack class="{{receipt | message | ?}}" id="{{message_id}}">
    </ack>
    '''

    def __init__(self, _id, _class,_error=None,_type=None) -> None:
        super().__init__("ack")
        self._id = _id
        self._class = _class
        self._error = _error
        self._type = _type        

    def getId(self) -> Any:
        return self._id

    def getClass(self) -> Any:
        return self._class
    
    def getError(self) -> Any:
        return self._error
    
    def getType(self) -> Any:
        return self._type
        
    def toProtocolTreeNode(self) -> Any:
        attribs = {
            "id"           : self._id,
            "class"        : self._class                    
        }

        if self._type :
            attribs["type"] = self._type

        return self._createProtocolTreeNode(attribs, None, data = None)

    def __str__(self):
        out  = "ACK:\n"
        out += "ID: %s\n" % self._id
        out += "Class: %s\n" % self._class

        if self._type is not None:
            out += "Type: %s\n" % self._type        

        if self._error is not None:
            out += "Error: %s\n" % self._error
            
        return out
        
    @staticmethod
    def fromProtocolTreeNode(node):
        return AckProtocolEntity(
            node.getAttributeValue("id"),
            node.getAttributeValue("class"),
            node.getAttributeValue("error"),
            node.getAttributeValue("type")
            )
