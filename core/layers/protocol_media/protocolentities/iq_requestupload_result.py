from ....common import YowConstants
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_iq.protocolentities import ResultIqProtocolEntity
from ....structs import ProtocolTreeNode
class ResultRequestUploadIqProtocolEntity(ResultIqProtocolEntity):
    def __init__(self, _id, url, ip = None, resumeOffset = 0, duplicate = False) -> None:
        super().__init__(_id = _id, _from = "s.whatsapp.net")
        self.setUploadProps(url, ip, resumeOffset, duplicate)

    def setUploadProps(self, url ,ip = None, resumeOffset = 0, duplicate = False) -> Any:
        self.url = url
        self.ip = ip
        self.resumeOffset = resumeOffset or 0
        self.duplicate = duplicate

    def isDuplicate(self) -> Any:
        return self.duplicate

    def getUrl(self) -> Any:
        return self.url

    def getResumeOffset(self) -> Any:
        return self.resumeOffset

    def getIp(self) -> Any:
        return self.ip

    def __str__(self):
        out = super().__str__()
        out += "URL: %s\n" % self.url
        if self.ip:
            out += "IP: %s\n" % self.ip
        return out

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()

        if not self.isDuplicate():
            mediaNode = ProtocolTreeNode("encr_media", {"url": self.url})
            if self.ip:
                mediaNode["ip"] = self.ip

            if self.resumeOffset:
                mediaNode["resume"] = str(self.resumeOffset)
        else:
            mediaNode = ProtocolTreeNode("duplicate", {"url": self.url})

        node.addChild(mediaNode)
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        entity= ResultIqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = ResultRequestUploadIqProtocolEntity
        mediaNode = node.getChild("encr_media")
        if mediaNode:
            entity.setUploadProps(mediaNode["url"], mediaNode["ip"], mediaNode["resume"])
        else:
            duplicateNode = node.getChild("duplicate")
            if duplicateNode:
                entity.setUploadProps(duplicateNode["url"], duplicateNode["ip"], duplicate = True)
        return entity
