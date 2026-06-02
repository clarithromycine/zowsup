from ....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_iq.protocolentities import IqProtocolEntity

class ResultStatusesIqProtocolEntity(IqProtocolEntity):
    '''
    <iq type="result" from="s.whatsapp.net" id="1">
        <status>
            <user jid="{number}@s.whatsapp.net" t="1330555420">
                {status message}
                HEX:{status message in hex}
            </user>
            <user jid="{number}@s.whatsapp.net" t="1420813055">
                {status message}
                HEX:{status message in hex}
            </user>
        </status>
    </iq>
    '''
    XMLNS = 'status'
    def __init__(self, _id, _from, statuses) -> None:
        super().__init__(self.__class__.XMLNS, _id, 'result', _from=_from)
        self.setResultStatusesProps(statuses)

    def setResultStatusesProps(self, statuses) -> Any:
        assert type(statuses) is dict, "statuses must be dict"
        self.statuses = statuses

    def __str__(self):
        out = super().__str__()
        out += "Statuses: %s\n" % ','.join(jid + '(' + str(v) + ')' for jid, v in self.statuses.items())
        return out

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        users = [ProtocolTreeNode('user', {'jid': jid, 't': t}, None, status) for jid, (status, t) in self.statuses.items()]
        statusNode = ProtocolTreeNode('status', None, users)
        node.addChild(statusNode)
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        statusNode = node.getChild('status')
        users = statusNode.getAllChildren()
        statuses = dict()
        for user in users:
            statuses[user['jid']] = (user.getData(), user['t'])

        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = ResultStatusesIqProtocolEntity
        entity.setResultStatusesProps(statuses)
        return entity
