from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes
import random
import time


class CallProtocolEntity(ProtocolEntity):
    """
    Generic call stanza entity. Covers all call types:
      offer, transport, relaylatency, reject, terminate, accept, etc.

    <call offline="0" from="{{CALLER_JID}}" id="{{ID}}" t="{{TIMESTAMP}}"
          notify="{{CALLER_PUSHNAME}}" retry="{{RETRY}}" e="{{?}}"
          to="{{CALLEE_JID}}">
        <offer .../>   <!-- or: <terminate/>, <reject/>, <transport/>, <relaylatency/> -->
    </call>

    For "offer" type, the factory fromProtocolTreeNode() returns a CallOffer instance
    (see call_offer.py) which carries the full offer sub-structure.
    """

    _HEX_CHARS = '0123456789ABCDEF'

    ID_TYPE_ANDROID = 0
    ID_TYPE_IOS = 1
    ID_TYPE_SMB_ANDROID = 2
    ID_TYPE_SMB_IOS = 3    

    # type -> (prefix, length)
    _CALL_ID_CONFIG = {
        ID_TYPE_ANDROID:     ("00", 30),
        ID_TYPE_IOS:         ("3A", 18),
        ID_TYPE_SMB_ANDROID: ("00", 30),
        ID_TYPE_SMB_IOS:     ("3A", 18),
    }

    _ID_CONFIG = {
        ID_TYPE_ANDROID:     ("AC", 30),
        ID_TYPE_IOS:         ("3A", 18),
        ID_TYPE_SMB_ANDROID: ("0D", 30),
        ID_TYPE_SMB_IOS:     ("3A", 18),
    }

    def _generateCallId(self, short=False, type=ID_TYPE_ANDROID):
        prefix, length = self._CALL_ID_CONFIG.get(type, ("00", 30))
        return prefix + ''.join(random.choices(self._HEX_CHARS, k=length))

    def _generateId(self, short=False, type=ID_TYPE_ANDROID):
        prefix, length = self._ID_CONFIG.get(type, ("00", 30))
        return prefix + ''.join(random.choices(self._HEX_CHARS, k=length))

    def __init__(self, callType,callCreator=None,callId=None,callMetaAttributes=None) -> None:

        """
        :type messageType: str
        :type messageMetaAttributes: MessageMetaAttributes
        """
        super().__init__("call")
        assert type(callMetaAttributes) is CallMetaAttributes

        self._type = callType       
        self._callCreator =  callCreator

        if callId is None:
            self._callId = self._generateCallId(type=callMetaAttributes.id)
        else:
            self._callId = callId

        if callMetaAttributes.id is None:
            callMetaAttributes.id = ProtocolEntity.ID_TYPE_ANDROID

        if callMetaAttributes.id in [0,1,2,3]:
            self._id = self._generateId(type=callMetaAttributes.id)      
        else:
            self._id = callMetaAttributes.id

        self._to = callMetaAttributes.recipient
        self._from = callMetaAttributes.sender
        self._timestamp = callMetaAttributes.timestamp 
        self._version = callMetaAttributes.version
        self._platform = callMetaAttributes.platform
        self._notify = callMetaAttributes.notify
        self._e = callMetaAttributes.e
        self._retry = callMetaAttributes.retry

        

    def __str__(self):
        out = "Call\n"
        if self._id is not None:
            out += "ID: %s\n" % self._id
        if self._from is not None:
            out += "From: %s\n" % self._from
        if self._to is not None:
            out += "To: %s\n" % self._to
        if self._type is not None:
            out += "Type: %s\n" % self._type
        if self._callId is not None:
            out += "Call ID: %s\n" % self._callId
        return out
    
    def isOutgoing(self) -> Any:
        return self._from is None

    def getFrom(self, full: bool = True) -> Any:
        return self._from if full else self._from.split('@')[0]

    def getTo(self) -> Any:
        return self._to

    def getId(self) -> Any:
        return self._id

    def getType(self) -> Any:
        return self._type
    
    def getCallCreator(self) -> Any:
        return self._callCreator

    def getCallId(self) -> Any:
        return self._callId

    def getTimestamp(self) -> Any:
        return self._timestamp

    def toProtocolTreeNode(self) -> ProtocolTreeNode:
        children = []
        attribs = {            
            "id": self._id,
        }
        if self._timestamp is not None:
            attribs["t"] = str(self._timestamp)
        if self._from is not None:
            attribs["from"] = self._from
        if self._to is not None:
            attribs["to"] = self._to
        if self._retry is not None:
            attribs["retry"] = str(self._retry)
        if self._e is not None:
            attribs["e"] = self._e
        if self._notify is not None:
            attribs["notify"] = self._notify
        if self._platform is not None:
            attribs["platform"] = self._platform
        if self._version is not None:
            attribs["version"] = self._version

        if self._type in ("offer", "preaccept","transport", "relaylatency", "reject", "terminate", "accept"):
            child_attrs = {}
            if self._callId is not None:
                child_attrs["call-id"] = self._callId
            if self._callCreator is not None:
                child_attrs["call-creator"] = self._callCreator

            children.append(ProtocolTreeNode(self._type, child_attrs))

        return self._createProtocolTreeNode(attribs, children=children, data=None)

    @staticmethod
    def fromProtocolTreeNode(node,proto=None):             
        """
        Factory: returns a CallOffer (subclass) for offer stanzas,
        or a plain CallProtocolEntity for other types.
        """
        _type = None
        _callId = None
        _callCreator = None

        for candidate in ("offer", "preaccept","transport", "relaylatency", "reject", "terminate", "accept"):
            child = node.getChild(candidate)
            if child is not None:
                _type = candidate
                _callId = child.getAttributeValue("call-id")
                _callCreator = child.getAttributeValue("call-creator")
                break
        
        if _type == "terminate":
            from .call_terminate import TerminateCallProtocolEntity
            return TerminateCallProtocolEntity.fromProtocolTreeNode(node)
        
        if _type == "reject":
            from .call_reject import RejectCallProtocolEntity
            return RejectCallProtocolEntity.fromProtocolTreeNode(node)

        return CallProtocolEntity(
            callType = _type,
            callId = _callId,
            callCreator = _callCreator,
            callMetaAttributes= CallMetaAttributes.from_call_protocoltreenode(node,proto)
        )

