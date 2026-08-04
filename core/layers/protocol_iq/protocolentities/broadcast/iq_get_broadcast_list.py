from ..iq import IqProtocolEntity
from typing import Optional, Any, List, Dict, Union
from .....structs import ProtocolTreeNode
from .....common import YowConstants

'''
<iq id="ACD93A07B8135A249607CFE56EDC4218" type="get" xmlns="w:b" to="s.whatsapp.net">
  <lists />
</iq>

'''

class GetBroadcastListProtocolEntity(IqProtocolEntity):
    def __init__(self) -> None:
        super().__init__("w:b", _type="get",to="s.whatsapp.net")

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        node.addChild(ProtocolTreeNode("lists"))
        return node


'''
<iq from="s.whatsapp.net" type="result" id="ACD93A07B8135A249607CFE56EDC4218">
  <lists>
    <list id="1784015469@broadcast" name="">
      <recipient jid="61947068346426@lid" pn_jid="14165843737@s.whatsapp.net" />
      <recipient jid="47945424572481@lid" pn_jid="66641399012@s.whatsapp.net" />
    </list>
    <list id="1784015594@broadcast" name="">
      <recipient jid="61947068346426@lid" pn_jid="14165843737@s.whatsapp.net" />
      <recipient jid="248846345101511@lid" pn_jid="8619874406144@s.whatsapp.net" />
      <recipient jid="16686635855888@lid" pn_jid="8618502065005@s.whatsapp.net" />
    </list>
  </lists>
</iq>
'''

class GetBroadcastListResultProtocolEntity(IqProtocolEntity):

    def __init__(self,_id=None, broadcastLists=None) -> None:
        super().__init__(_id = _id, _type = "result", to=YowConstants.DOMAIN)
        self.broadcastLists = broadcastLists or []

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = GetBroadcastListResultProtocolEntity

        entity.broadcastLists = []
        listsNode = node.getChild("lists")
        if listsNode is not None:
            for listNode in listsNode.getAllChildren():
                if listNode.tag != "list":
                    continue
                broadcastList = {
                    "id": listNode.getAttributeValue("id"),
                    "name": listNode.getAttributeValue("name"),
                    "recipients": []
                }
                for recipientNode in listNode.getAllChildren():
                    if recipientNode.tag != "recipient":
                        continue
                    recipient = {
                        "jid": recipientNode.getAttributeValue("jid"),
                        "pn_jid": recipientNode.getAttributeValue("pn_jid")
                    }
                    broadcastList["recipients"].append(recipient)
                entity.broadcastLists.append(broadcastList)

        return entity
    