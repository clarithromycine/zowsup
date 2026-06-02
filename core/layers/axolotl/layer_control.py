from .layer_base import AxolotlBaseLayer
from typing import Optional, Any, List, Dict, Union
from ...layers import YowLayerEvent, EventCallback
from ...layers.network.layer import YowNetworkLayer
from ...layers.axolotl.protocolentities import *
from ...layers.auth.layer_authentication import YowAuthenticationProtocolLayer
from ...layers.protocol_acks.protocolentities import OutgoingAckProtocolEntity
from ...layers.protocol_iq.protocolentities          import *
from ...layers.protocol_ib.protocolentities          import *
from ...axolotl.manager import AxolotlManager
from axolotl.util.hexutil import HexUtil
from axolotl.ecc.curve import Curve

import logging
import binascii
import base64

logger = logging.getLogger(__name__)

class AxolotlControlLayer(AxolotlBaseLayer):
    def __init__(self) -> None:
        super().__init__()
        self._unsent_prekeys = []
        self._reboot_connection = False

    async def send(self, node) -> Any:       

        await self.toLower(node)

    async def receive(self, protocolTreeNode) -> Any:

        """
        :type protocolTreeNode: ProtocolTreeNode
        """
        if not await self.processIqRegistry(protocolTreeNode):
            if protocolTreeNode.tag == "notification" and protocolTreeNode["type"] == "encrypt":
                if protocolTreeNode.getChild("count") is not None:
                    return await self.onRequestKeysEncryptNotification(protocolTreeNode)
                elif protocolTreeNode.getChild("identity") is not None:
                    return await self.onIdentityChangeEncryptNotification(protocolTreeNode)

            await self.toUpper(protocolTreeNode)

    async def onIdentityChangeEncryptNotification(self, protocoltreenode) -> Any:
        entity = IdentityChangeEncryptNotification.fromProtocolTreeNode(protocoltreenode)
        ack = OutgoingAckProtocolEntity(
            protocoltreenode["id"], "notification", protocoltreenode["type"], protocoltreenode["from"]
        )
        await self.toLower(ack.toProtocolTreeNode())
        await self.getKeysFor([entity.getFrom(True)], resultClbk=lambda _,__: None, reason="identity")

    async def onRequestKeysEncryptNotification(self, protocolTreeNode) -> Any:
        entity = RequestKeysEncryptNotification.fromProtocolTreeNode(protocolTreeNode)
        ack = OutgoingAckProtocolEntity(protocolTreeNode["id"], "notification", protocolTreeNode["type"], protocolTreeNode["from"])
        await self.toLower(ack.toProtocolTreeNode())

        if self.getProp("HC_MODE",False) or self.getProp("BC_MODE",False) or self.getProp("TRANSFER6_MODE",False):
            pass
        else:
            await self.flush_keys(
                self.manager.generate_signed_prekey(),
                self.manager.level_prekeys(force=True)
            )

    @EventCallback(YowNetworkLayer.EVENT_STATE_CONNECTED)
    def on_connected(self, yowLayerEvent) -> Any:
        super().on_connected(yowLayerEvent)
        
        if self.manager is not None:            
            if self.getProp("HC_MODE",False) or self.getProp("BC_MODE",False) or self.getProp("TRANSFER6_MODE"):
                self.setProp(YowAuthenticationProtocolLayer.PROP_PASSIVE, False)            
            else :        
                self.manager.level_prekeys()                
                self._unsent_prekeys.extend(self.manager.load_unsent_prekeys())           
                if len(self._unsent_prekeys):
                    self.setProp(YowAuthenticationProtocolLayer.PROP_PASSIVE, True)
    
    @EventCallback(YowAuthenticationProtocolLayer.EVENT_AUTHED)
    async def onAuthed(self, yowLayerEvent) -> Any:
        

        usib = UnifiedSessionIbProtocolEntity()
        await self.toLower(usib.toProtocolTreeNode())


        profile = self.getStack().getProp("profile")
        if profile.config.fcm_cat is not None:
            catib = CatIbProtocolEntity(catdata=base64.b64decode(profile.config.fcm_cat))
            await self.toLower(catib.toProtocolTreeNode())

        if self.getProp(YowAuthenticationProtocolLayer.PROP_PASSIVE, False):
            self.manager.level_prekeys()
            
            self._unsent_prekeys.extend(self.manager.load_unsent_prekeys())  
            logger.debug("SHOULD FLUSH KEYS %d NOW!!" % len(self._unsent_prekeys))
            await self.flush_keys(
                self.manager.load_latest_signed_prekey(generate=True),
                self._unsent_prekeys[:], 
                reboot_connection=True
            )
            self._unsent_prekeys = []                    

        
    @EventCallback(YowNetworkLayer.EVENT_STATE_DISCONNECTED)
    async def on_disconnected(self, yowLayerEvent) -> Any:        
        super().on_disconnected(yowLayerEvent)
        logger.debug("Disconnected, reboot_connect? = %s" % self._reboot_connection)        
        if self._reboot_connection:
            self._reboot_connection = False         
            self.setProp(YowAuthenticationProtocolLayer.PROP_PASSIVE, False)
            await self.getLayerInterface(YowNetworkLayer).connect()

    async def flush_keys(self, signed_prekey, prekeys, reboot_connection=False) -> Any:    
        preKeysDict = {}
        for prekey in prekeys:
            keyPair = prekey.getKeyPair()
            preKeysDict[self.adjustId(prekey.getId())] = self.adjustArray(keyPair.getPublicKey().serialize()[1:])

        signedKeyTuple = (self.adjustId(signed_prekey.getId()),
                        self.adjustArray(signed_prekey.getKeyPair().getPublicKey().serialize()[1:]),
                        self.adjustArray(signed_prekey.getSignature()))

        self.adjustId(self.manager.registration_id,byte_count=4)
        setKeysIq = SetKeysIqProtocolEntity(
            self.adjustArray(
                self.manager.identity.getPublicKey().serialize()[1:]
            ),
            signedKeyTuple,
            preKeysDict,
            Curve.DJB_TYPE,
            self.adjustId(self.manager.registration_id,byte_count=4) 
        )
        onResult = lambda _, __: self.on_keys_flushed(prekeys, reboot_connection=reboot_connection)
        await self._sendIq(setKeysIq, onResult, self.onSentKeysError)            

    async def on_keys_flushed(self, prekeys, reboot_connection) -> Any:
        self.manager.set_prekeys_as_sent(prekeys)        
        if reboot_connection:            
            self._reboot_connection = True            
            await self.broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT))

    async def onSentKeysError(self, errorNode, keysEntity) -> Any:
        logger.info("Sent keys were not accepted")      
        if not self.getProp("REPAIRFCM_ING",False):
            self.setProp("REPAIRFCM", True)
            await self.broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT))        


    def adjustArray(self, arr) -> Any:
        return HexUtil.decodeHex(binascii.hexlify(arr))
    
    def adjustId(self, _id,byte_count=3) -> Any:
        _id = format(_id, 'x')
        zfiller = len(_id) if len(_id) % 2 == 0 else len(_id) + 1
        _id = _id.zfill(zfiller if zfiller > byte_count*2 else byte_count*2)
        return binascii.unhexlify(_id)
