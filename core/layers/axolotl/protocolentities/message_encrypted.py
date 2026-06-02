from ....layers.protocol_messages.protocolentities import MessageProtocolEntity
from typing import Optional, Any, List, Dict, Union
from ....structs import ProtocolTreeNode
from ....layers.axolotl.protocolentities.enc import EncProtocolEntity
class EncryptedMessageProtocolEntity(MessageProtocolEntity):
    '''
    <message retry="1" from="49xxxxxxxx@s.whatsapp.net" t="1418906418" offline="1" type="text" id="1418906377-1" notify="Tarek Galal">
<enc type="{{type}}" mediatype="image|audio|location|document|contact" v="{{1 || 2}}">
HEX:33089eb3c90312210510e0196be72fe65913c6a84e75a54f40a3ee290574d6a23f408df990e718da761a210521f1a3f3d5cb87fde19fadf618d3001b64941715efd3e0f36bba48c23b08c82f2242330a21059b0ce2c4720ec79719ba862ee3cda6d6332746d05689af13aabf43ea1c8d747f100018002210d31cd6ebea79e441c4935f72398c772e2ee21447eb675cfa28b99de8d2013000</enc>

</message>
    '''

    def __init__(self, encEntities, _type, messageAttributes) -> None:
        super().__init__(_type, messageAttributes)
        self.attrs = messageAttributes
        self.setEncEntities(encEntities)

    def setEncEntities(self, encEntities = None) -> Any:
        assert type(encEntities) is list and len(encEntities) \
            , "Must have at least a list of minumum 1 enc entity"
        self.encEntities = encEntities

    def getEnc(self, encType) -> Any:
        for enc in self.encEntities:
            if enc.type == encType:
                return enc

    def getEncEntities(self) -> Any:
        return self.encEntities

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()
        
        if self.attrs is not None and self.attrs.category == "peer":
            #peer-msg单发
            encNode = self.encEntities[0]
            node.addChild(ProtocolTreeNode("meta",{"appdata":"default"}))            
            node.addChild(encNode.toProtocolTreeNode())
        else:
            #正常多发        
            participantsNode = ProtocolTreeNode("participants")
            for enc in self.encEntities:
                encNode = enc.toProtocolTreeNode()                
                if encNode.tag == "to":                                                                                
                    participantsNode.addChild(encNode)                                        
                else:
                    node.addChild(encNode)
                                            
            if len(participantsNode.getAllChildren()):
                node.addChild(participantsNode)
                        
        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = MessageProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = EncryptedMessageProtocolEntity
        entity.attrs = None
        entity.setEncEntities(
            [EncProtocolEntity.fromProtocolTreeNode(encNode) for encNode in node.getAllChildren("enc")]
        )
        return entity
