from ....common import YowConstants
from ....layers.protocol_iq.protocolentities import IqProtocolEntity
from ....structs import ProtocolTreeNode
import logging

logger = logging.getLogger(__name__)


class SetStatusIqProtocolEntity(IqProtocolEntity):
    '''
    <iq to="s.whatsapp.net" xmlns="status" type="set" id="{{IQ_ID}}">
        <status>{{MSG}}</status>
    </notification>
    '''
    XMLNS = "status"
    def __init__(self, text = None, _id = None):
        if type(text) is not bytes:
            logger.warning("Passing text as str is deprecated, pass bytes instead")
            text = bytes(text, "latin-1")
        super(SetStatusIqProtocolEntity, self).__init__(self.__class__.XMLNS, _id, _type = "set", to = YowConstants.WHATSAPP_SERVER)
        self.setData(text)

    def setData(self, text):
        self.text = text

    def toProtocolTreeNode(self):
        node = super(SetStatusIqProtocolEntity, self).toProtocolTreeNode()
        statusNode = ProtocolTreeNode("status", {}, [], self.text)
        node.addChild(statusNode)
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = SetStatusIqProtocolEntity
        statusNode = node.getChild("status")
        entity.setData(statusNode.getData())
        return entity
