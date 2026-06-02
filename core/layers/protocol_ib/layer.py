from ...layers import YowProtocolLayer
from typing import Optional, Any, List, Dict, Union
from .protocolentities import *
from ..protocol_iq.protocolentities import CleanDirtyIqProtocolEntity
import logging

logger = logging.getLogger(__name__)


class YowIbProtocolLayer(YowProtocolLayer):

    def __init__(self) -> None:
        handleMap = {
            "ib": (self.recvIb, self.sendIb),
            #"iq": (None, self.sendIb)
        }
        super().__init__(handleMap)

    def __str__(self):
        return "Ib Layer"

    async def sendIb(self, entity) -> Any:
        node =     entity.toProtocolTreeNode()    
        await self.toLower(node)
        
    async def recvIb(self, node) -> Any:
        if node.getChild("dirty"):
            dirty_node = node.getChild("dirty")
            logger.info("auto clean %s" % dirty_node["type"])
            clean = CleanDirtyIqProtocolEntity(type=dirty_node["type"])
            await self.toLower(clean.toProtocolTreeNode())
        elif node.getChild("offline"):
            await self.toUpper(OfflineIbProtocolEntity.fromProtocolTreeNode(node))
        elif node.getChild("edge_routing"):            
            entity = EdgeRoutingIbProtocolEntity.fromProtocolTreeNode(node)
            profile = self.getProp("profile")            
            if profile.config.edge_routing_info!=entity.routing_info:
                profile.config.edge_routing_info = entity.routing_info
                profile.write_config(profile.config)            
                logger.info("edge_routing_info change")                      
        elif node.getChild("attestation"):
            logger.info("ignoring attestation ib node")
        elif node.getChild("fbip"):
            logger.info("ignoring fbip ib node")
        elif node.getChild("notice"):
            logger.info("ignoring notice ib node")
        elif node.getChild("safetynet"):
            logger.info("recevice a safetynet request")    
            await self.toUpper(SafetynetRequestIbProtocolEntity.fromProtocolTreeNode(node))           
        elif node.getChild("gpia"):
            logger.info("receive a gpia request")
            await self.toUpper(GpiaRequestIbProtocolEntity.fromProtocolTreeNode(node))            
        elif node.getChild("offline_preview"):
            logger.info(node)
        else:
            logger.warning("Unsupported ib node: \n%s" % node)
