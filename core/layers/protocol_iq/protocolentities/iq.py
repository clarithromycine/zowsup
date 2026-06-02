from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
class IqProtocolEntity(ProtocolEntity):

    '''
    <iq type="{{get | set}}" id="{{id}}" xmlns="{{xmlns}}" to="{{to}}" from="{{from}}" target="{{target}} "smax_id="{{max_id}}">
    </iq>
    '''

    TYPE_SET = "set"
    TYPE_GET = "get"
    TYPE_ERROR = "error"
    TYPE_RESULT = "result"

    TYPES = (TYPE_SET, TYPE_GET, TYPE_RESULT, TYPE_ERROR)
    def __init__(self, xmlns = None, _id = None, _type = None, to = None, _from = None,target=None,smax_id=None) -> None:
        super().__init__("iq")

        #assert _type in self.__class__.TYPES, "Iq of type %s is not implemented, can accept only (%s)" % (_type," | ".join(self.__class__.TYPES))
        assert not to or not _from, "Can't set from and to at the same time"

        if _id is None:
            _id = ProtocolEntity.ID_TYPE_ANDROID        

        if _id in [0,1,2,3]:
            self._id = self._generateId(True,type=_id)
        else:
            self._id = _id
        
        self._from = _from
        self._type = _type
        self.xmlns = xmlns
        self.to = to
        self.target = target

        self.smax_id = smax_id

    def getId(self) -> Any:
        return self._id

    def getType(self) -> Any:
        return self._type

    def getXmlns(self) -> Any:
        return self.xmlns

    def getFrom(self, full = True) -> Any:
        
        if self.participant is not None:
            return (self.participant if full else self.participant.split('@')[0] ) +"#"+ (self._from if full else self._from.split('@')[0] )
        else :
            return self._from if full else self._from.split('@')[0]

    def getTo(self) -> Any:
        return self.to
    
    def getSmaxId(self) -> Any:
        return self.smax_id
    
    def toProtocolTreeNode(self) -> Any:
        attribs = {
            "id"          : self._id,
            "type"        : self._type            
        }

        if self.xmlns:
            attribs["xmlns"] = self.xmlns

        if self.target:
            attribs["target"] = self.target
            
        if self.to :
            attribs["to"] = self.to
        elif self._from:
            attribs["from"] = self._from

        if self.smax_id:
            attribs["smax_id"] = self.smax_id #"87"

        return self._createProtocolTreeNode(attribs, None, data = None)

    def __str__(self):
        out  = "Iq:\n"
        out += "ID: %s\n" % self._id
        out += "Type: %s\n" % self._type
        if self.xmlns:
            out += "xmlns: %s\n" % self.xmlns
        if self.to:
            out += "to: %s\n" % self.to
        elif self._from:
            out += "from: %s\n" % self._from

        if self.smax_id:
            out += "smax_id: %s\n" % self.smax_id
        return out

    @staticmethod
    def fromProtocolTreeNode(node):
        return IqProtocolEntity(
            node.getAttributeValue("xmlns"),
            node.getAttributeValue("id"),
            node.getAttributeValue("type"),
            node.getAttributeValue("to"),
            node.getAttributeValue("from"),
            node.getAttributeValue("target"),
            node.getAttributeValue("smax_id")
            )
