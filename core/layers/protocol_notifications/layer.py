from ...layers import YowLayer, YowLayerEvent, YowProtocolLayer
from typing import Optional, Any, List, Dict, Union
from .protocolentities import *

from ...layers.protocol_acks.protocolentities import OutgoingAckProtocolEntity
import logging


logger = logging.getLogger(__name__)


class YowNotificationsProtocolLayer(YowProtocolLayer):

    def __init__(self) -> None:
        handleMap = {
            "notification": (self.recvNotification, self.sendNotification)
        }
        super().__init__(handleMap)

    def __str__(self):
        return "notification Ib Layer"

    async def sendNotification(self, entity) -> Any:
        if entity.getTag() == "notification":
            await self.toLower(entity.toProtocolTreeNode())

    async def recvNotification(self, node) -> Any:

        if node["type"] == "mex":            
            await self.toUpper(MexUpdateNotificationProtocolEntity.fromProtocolTreeNode(node))            

        elif node["type"] == "account_sync":
            await self.toUpper(AccountSyncNotificationProtocolEntity.fromProtocolTreeNode(node))

        elif node["type"] == "server_sync":
            await self.toUpper(ServerSyncNotificationProtocolEntity.fromProtocolTreeNode(node))

        elif node["type"] == "link_code_companion_reg":
            logger.debug("link_code_companion_reg: %s", node)
            await self.toUpper(LinkCodeCompanionRegNotificationProtocolEntity.fromProtocolTreeNode(node))
            
        elif node["type"] == "registration":
            if node.getChild("wa_old_registration"):
                await self.toUpper(WaOldCodeNotificationProtocolEntity.fromProtocolTreeNode(node))
            elif node.getChild("device_logout"):
                await self.toUpper(DeviceLogoutNotificationProtocolEntity.fromProtocolTreeNode(node))
            else:
                logger.warning("Unsupported notification subnode in registration node")     
                logger.debug(node)

        elif node["type"] == "business":            
            if node.getChild("verified_name"):                    
                n = node.getChild("verified_name")
                #有可能收到别人的，或者自己的
                if n.getAttributeValue("jid") is not None:
                    await self.toUpper(BusinessNameUpdateNotificationProtocolEntity.fromProtocolTreeNode(node))
                else:
                    logger.debug("business verified_name without jid: %s", node)
            elif node.getChild("remove"):
                await self.toUpper(BusinessRemoveNotificationProtocolEntity.fromProtocolTreeNode(node))
            else:
                #business实现不太完整，如果有其他的子节点，打印出来
                logger.warning("Unsupported notification subnode in business node")  
                logger.debug(node)

        elif node["type"] == "disappearing_mode":  
            if node.getChild("disappearing_mode"):
                await self.toUpper(DisapperingModeNotificationProtocolEntity.fromProtocolTreeNode(node))            

        elif node["type"] == "picture":
            if node.getChild("set"):
                await self.toUpper(SetPictureNotificationProtocolEntity.fromProtocolTreeNode(node))
            elif node.getChild("delete"):
                await self.toUpper(DeletePictureNotificationProtocolEntity.fromProtocolTreeNode(node))
            elif node.getChild("set_avatar"):
                #这个好像是新特性，先忽略异常
                pass
            else:
                self.raiseErrorForNode(node)
        elif node["type"] == "status":
            await self.toUpper(StatusNotificationProtocolEntity.fromProtocolTreeNode(node))
            
        elif node["type"] in ["contacts", "subject", "w:gp2","devices"]:
            # Implemented in respectively the protocol_contacts,protocol_devices and protocol_groups layer
            pass
            
        elif node["type"] == "privacy_token":        
            logger.info("receive a privacy_token from %s",node["from"].split("@")[0])         
            jid = lid = tctoken = tctoken_ts = None
            tokens = node.getChild("tokens")
            if tokens:
                token = tokens.getAllChildren()[0]
                if token["type"] == "trusted_contact":
                    if node["from"].endswith("lid"):
                        jid = node["sender_pn"]
                        lid = node["from"]
                    else:
                        jid = node["from"]
                        lid = node["sender_lid"]
                    tctoken = token.getData()
                    tctoken_ts = int(token.getAttributeValue("t"))
            db = self.getStack().getProp("profile").axolotl_manager
            db._store.updateTctoken(jid=jid, lid=lid, tctoken=tctoken, tctoken_ts=tctoken_ts)
                                
        elif node["type"] == "psa":            
            logger.info("receive a psa node,ignoring it ")            
        elif node["type"] == "server":     
            if node.getChild("push-config"):
                await self.toUpper(ServerPushConfigNotificationProtocolEntity.fromProtocolTreeNode(node))
            else:
                logger.warning("Unsupported notification type: %s " % node["type"])            
                logger.debug(node)
        else:                   
            logger.warning("Unsupported notification type: %s " % node["type"])            
            logger.debug(node)

        ack = OutgoingAckProtocolEntity(node["id"], "notification", node["type"], node["from"], participant=node["participant"])
        await self.toLower(ack.toProtocolTreeNode())






