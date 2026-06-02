from ....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_iq.protocolentities import ResultIqProtocolEntity
class SuccessAddParticipantsIqProtocolEntity(ResultIqProtocolEntity):
    '''
    <iq type="result" from="{{group_jid}}" id="{{id}}">
        <add>
            <participant jid="{{jid}}" error="{{errno}}/>
            <participant jid="{{jid}}" error="{{errno}}/>
            ...
        </add>
    </iq>
    '''

    def __init__(self, _id, groupId, successList,errorList) -> None:
        super().__init__(_from = groupId, _id = _id)
        self.setProps(groupId, successList,errorList)

    def setProps(self, groupId, successList,errorList) -> Any:
        self.groupId = groupId
        self.successList = successList
        self.errorList = errorList
        self.action = 'add'

    def getAction(self) -> Any:
        return self.action

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = ResultIqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = SuccessAddParticipantsIqProtocolEntity
        successList = []
        errorList = []
        list = node.getChild("add")
        for participantNode in list.getAllChildren():
            if participantNode["error"] is None:
                successList.append(participantNode["jid"])
            else:
                errorList.append([participantNode["jid"],participantNode["error"]])
        entity.setProps(node.getAttributeValue("from"), successList,errorList)
        return entity
