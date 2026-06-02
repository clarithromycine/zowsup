from .notification import NotificationProtocolEntity
from typing import Optional, Any, List, Dict, Union
from proto import e2e_pb2
class BusinessNameUpdateNotificationProtocolEntity(NotificationProtocolEntity):
    '''
    <notification from="56933533874@s.whatsapp.net" type="business" id="2118190199" t="1740411082">
        <verified_name verified_level="unknown" serial="3235401012801303250" jid="56933533874@s.whatsapp.net" v="1">
            0x0a2208d2e5d7cfc4829df32c1206736d623a7761220e436f7261204d69746368656c6c781240b67125860cced7dcbbe8ca2756c30d8d4305ea1b8992e264956fcd1e4238d2e67e78fb7389f66faf8591d62a8da144b3cabcc52da09ba78b9692d2d7e8ca910b
        </verified_name>
    </notification>
    '''

    def __init__(self, _id,  _from,  timestamp, notify, offline, verified_level,serial,jid, v, name) -> None:
        super().__init__("business",_id, _from, timestamp, notify, offline)
        self.setData(verified_level, serial, jid, v, name)

    def setData(self, verified_level, serial,jid,v,name) -> Any:
        self.verified_level  =  verified_level
        self.serial =   serial
        self.jid = jid  
        self.v = v
        self.name = name

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = NotificationProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = BusinessNameUpdateNotificationProtocolEntity
        verifyNameNode = node.getChild("verified_name")
        verify_level = verifyNameNode.getAttributeValue("verified_level")
        serial = verifyNameNode.getAttributeValue("serial")
        jid = verifyNameNode.getAttributeValue("jid")
        v = verifyNameNode.getAttributeValue("v")
        data = verifyNameNode.getData()
        name = ""
        if data is not None:
            vnc = e2e_pb2.VerifiedNameCertificate()
            vnc.ParseFromString(data)
            name = vnc.details.verifiedName        
        entity.setData(verify_level,serial,jid,v,name)
        return entity