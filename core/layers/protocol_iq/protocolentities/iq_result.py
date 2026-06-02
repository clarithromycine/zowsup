from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .iq import IqProtocolEntity
class ResultIqProtocolEntity(IqProtocolEntity):

    '''
    <iq type="result" id="{{id}}" from="{{FROM}}">
    </iq>
    '''

    def __init__(self, xmlns = None, _id = None, to = None, _from = None) -> None:
        super().__init__(xmlns = xmlns, _id = _id, _type = "result", to = to, _from = _from)


    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = ResultIqProtocolEntity
        return entity

