from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .ib import IbProtocolEntity
class OfflineIbProtocolEntity(IbProtocolEntity):
    '''
    <ib from="s.whatsapp.net">
        <offline count="{{X}}"></offline>
    </ib>
    '''
    def __init__(self, count) -> None:
        super(IbProtocolEntity, self).__init__()
        self.setProps(count)

    def setProps(self, count) -> Any:
        self.count = int(count)
    
    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        offlineChild = ProtocolTreeNode("offline", {"count": str(self.count)})
        node.addChild(offlineChild)
        return node

    def __str__(self):
        out = super().__str__()
        out += "ib-offline count: %s\n" % self.count
        return out

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IbProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = OfflineIbProtocolEntity
        entity.setProps(node.getChild("offline")["count"])
        return entity
    
class OfflinePreviewIbProtocolEntity(IbProtocolEntity):
    '''
    <ib from="s.whatsapp.net">
        <offline_preview count="4" message="0" receipt="0" notification="4" appdata="0" call="0" status="0" />
    </ib>
    '''
    def __init__(self, count,message,receipt,notification,appdata,call,status) -> None:
        super(IbProtocolEntity, self).__init__()
        self.setProps(count,message,receipt,notification,appdata,call,status)

    def setProps(self, count,message,receipt,notification,appdata,call,status) -> Any:
        self.count = int(count)
        self.message = int(message)
        self.receipt = int(receipt)
        self.notification = int(notification)
        self.appdata = int(appdata)
        self.call = int(call)
        self.status = int(status)
    
    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        offlineChild = ProtocolTreeNode("offline", {
            "count": str(self.count),
            "message":str(self.message),
            "receipt":str(self.receipt),
            "notification":str(self.notification),
            "appdata":str(self.appdata),
            "call":str(self.call),
            "status":str(self.status)
        })
        node.addChild(offlineChild)
        return node

    def __str__(self):
        out = super().__str__()
        out += "ib-offline-preview count:%d message:%d receipt:%d notification:%d appdata:%d call:%d status:%d\n" % (
            self.count,self.message,self.receipt,self.notification,self.appdata,self.call,self.status
        )
        return out

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IbProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = OfflinePreviewIbProtocolEntity
        previewNode = node.getChild("offline_preview")
        entity.setProps(
            previewNode.getAttributeValue("count"),
            previewNode.getAttributeValue("message"),
            previewNode.getAttributeValue("receipt"),
            previewNode.getAttributeValue("notification"),
            previewNode.getAttributeValue("appdata"),
            previewNode.getAttributeValue("call"),
            previewNode.getAttributeValue("status")
        )
        return entity

