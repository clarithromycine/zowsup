from ....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .receipt import ReceiptProtocolEntity
class OutgoingReceiptProtocolEntity(ReceiptProtocolEntity):

    '''
    delivered:
    If we send the following without "to" specified, whatsapp will consider the message delivered,
    but will not notify the sender.
    <receipt to="xxxxxxxxxxx@s.whatsapp.net" id="1415389947-15"></receipt>

    read
    <receipt to="xxxxxxxxxxx@s.whatsapp.net" id="1415389947-15" type="read"></receipt>

    multiple items:
    <receipt type="read" to="xxxxxxxxxxxx@s.whatsapp.net" id="1431364583-191">
        <list>
            <item id="1431364572-189"></item>
            <item id="1431364575-190"></item>
        </list>
    </receipt>
    '''


    def __init__(self, messageIds, to, read = False, participant = None,recipient=None, callId = None,view=False,serverIds=None,histSync=None,peerMsg=None) -> None:
        if type(messageIds) in (list, tuple):
            if len(messageIds) > 1:
                receiptId = self._generateId()
            else:
                receiptId = messageIds[0]
        else:
            receiptId = messageIds
            messageIds = [messageIds]

        if serverIds is not None:    
            if type(serverIds) in (list, tuple):
                serverIds = serverIds
            else:
                serverIds = [serverIds]

        super().__init__(receiptId)
        self.setOutgoingData(messageIds, to, read, participant,recipient, callId,view,serverIds,histSync,peerMsg)

    def setOutgoingData(self, messageIds, to, read, participant,recipient=None, callId=None,view=None, serverIds=None,histSync=None,peerMsg=None) -> Any:
        self.messageIds = messageIds
        self.to = to
        self.read = read
        self.participant = participant
        self.callId = callId
        self.view = view
        self.serverIds = serverIds
        self.recipient = recipient
        self.histSync = histSync
        self.peerMsg = peerMsg

    def getMessageIds(self) -> Any:
        return self.messageIds

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        if self.read:
            node.setAttribute("type", "read")

        if self.view:
            node.setAttribute("type","view")

        if self.histSync:
            node.setAttribute("type","hist_sync")

        if self.peerMsg:
            node.setAttribute("type","peer_msg")

        if self.participant:
            node.setAttribute("participant", self.participant)

        if self.recipient:
            node.setAttribute("recipient", self.recipient)

        if self.callId:
            offer = ProtocolTreeNode("offer", {"call-id": self.callId})
            node.addChild(offer)

        if self.to:
            node.setAttribute("to", self.to)

        if len(self.messageIds) > 1:
            listNode = ProtocolTreeNode("list")
            listNode.addChildren([ProtocolTreeNode("item", {"id": mId}) for mId in self.messageIds])
            node.addChild(listNode)

        if self.serverIds is not None and len(self.serverIds)>0:
            listNode = ProtocolTreeNode("list")
            listNode.addChildren([ProtocolTreeNode("item", {"server_id": sId}) for sId in self.serverIds])
            node.addChild(listNode)

        return node

    def __str__(self):
        out = super().__str__()
        out  += "To: \n%s" % self.to
        if self.read:
            out += "Type: \n%s" % "read"
        out += "For: \n%s" % self.messageIds
        return out

    @staticmethod
    def fromProtocolTreeNode(node):
        listNode = node.getChild("list")
        messageIds = []
        if listNode:
            messageIds = [child["id"] for child in listNode.getChildren()]
        else:
            messageIds = [node["id"]]

        return OutgoingReceiptProtocolEntity(
            messageIds,
            node["to"],
            node["type"] == "read",
            node["participant"],
            node["recipient"] if node.hasAttribute("recipient") else None,
            node["call-id"] if node.hasAttribute("call-id") else None,
            node["type"] == "view",
            node["server_id"] if node.hasAttribute("server_id") else None,
            node["type"] == "hist_sync",
            node["type"] == "peer_msg"     
        )
