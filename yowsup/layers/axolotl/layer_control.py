from .layer_base import AxolotlBaseLayer
from ...layers import YowLayerEvent, EventCallback
from ...layers.network.layer import YowNetworkLayer
from ...layers.axolotl.protocolentities import *
from ...layers.auth.layer_authentication import YowAuthenticationProtocolLayer
from ...layers.protocol_acks.protocolentities import OutgoingAckProtocolEntity
from ...layers.protocol_iq.protocolentities          import *
from ...layers.protocol_ib.protocolentities          import *
from axolotl.util.hexutil import HexUtil
from axolotl.ecc.curve import Curve
import logging
import binascii
import base64

logger = logging.getLogger(__name__)

class AxolotlControlLayer(AxolotlBaseLayer):
    def __init__(self):
        super(AxolotlControlLayer, self).__init__()
        self._unsent_prekeys = []
        self._reboot_connection = False

    def send(self, node):       

        self.toLower(node)

    def receive(self, protocolTreeNode):

        """
        :type protocolTreeNode: ProtocolTreeNode
        """
        if not self.processIqRegistry(protocolTreeNode):
            if protocolTreeNode.tag == "notification" and protocolTreeNode["type"] == "encrypt":
                if protocolTreeNode.getChild("count") is not None:
                    return self.onRequestKeysEncryptNotification(protocolTreeNode)
                elif protocolTreeNode.getChild("identity") is not None:
                    return self.onIdentityChangeEncryptNotification(protocolTreeNode)

            self.toUpper(protocolTreeNode)

    def onIdentityChangeEncryptNotification(self, protocoltreenode):
        entity = IdentityChangeEncryptNotification.fromProtocolTreeNode(protocoltreenode)
        ack = OutgoingAckProtocolEntity(
            protocoltreenode["id"], "notification", protocoltreenode["type"], protocoltreenode["from"]
        )
        self.toLower(ack.toProtocolTreeNode())
        self.getKeysFor([entity.getFrom(True)], resultClbk=lambda _,__: None, reason="identity")

    def onRequestKeysEncryptNotification(self, protocolTreeNode):
        entity = RequestKeysEncryptNotification.fromProtocolTreeNode(protocolTreeNode)
        ack = OutgoingAckProtocolEntity(protocolTreeNode["id"], "notification", protocolTreeNode["type"], protocolTreeNode["from"])
        self.toLower(ack.toProtocolTreeNode())
        self.flush_keys(
            self.manager.generate_signed_prekey(),
            self.manager.level_prekeys(force=True)
        )

    @EventCallback(YowNetworkLayer.EVENT_STATE_CONNECTED)
    def on_connected(self, yowLayerEvent):
        super(AxolotlControlLayer, self).on_connected(yowLayerEvent)
        if self.manager is not None:               
            self.manager.level_prekeys()
            self._unsent_prekeys.extend(self.manager.load_unsent_prekeys())           
            if len(self._unsent_prekeys):
                self.setProp(YowAuthenticationProtocolLayer.PROP_PASSIVE, True)
    
    @EventCallback(YowAuthenticationProtocolLayer.EVENT_AUTHED)
    def onAuthed(self, yowLayerEvent):
       
        if yowLayerEvent.getArg("passive") and len(self._unsent_prekeys):

            profile = self.getStack().getProp("profile")
            if profile.config.fcm_cat is not None:
                ib = CatIbProtocolEntity(catdata=base64.b64decode(profile.config.fcm_cat))
                self.toLower(ib.toProtocolTreeNode())

            logger.debug("SHOULD FLUSH KEYS %d NOW!!" % len(self._unsent_prekeys))
            self.flush_keys(
                self.manager.load_latest_signed_prekey(generate=True),
                self._unsent_prekeys[:], reboot_connection=True
            )
            self._unsent_prekeys = []                    
        
        

    @EventCallback(YowNetworkLayer.EVENT_STATE_DISCONNECTED)
    def on_disconnected(self, yowLayerEvent):        
        super(AxolotlControlLayer, self).on_disconnected(yowLayerEvent)
        logger.debug(("Disconnected, reboot_connect? = %s" % self._reboot_connection))
        if self._reboot_connection:
            self._reboot_connection = False         
            self.setProp(YowAuthenticationProtocolLayer.PROP_PASSIVE, False)
            self.getLayerInterface(YowNetworkLayer).connect()

    def flush_keys(self, signed_prekey, prekeys, reboot_connection=False):    
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
        self._sendIq(setKeysIq, onResult, self.onSentKeysError)            

    def on_keys_flushed(self, prekeys, reboot_connection):
        self.manager.set_prekeys_as_sent(prekeys)        
        if reboot_connection:            
            self._reboot_connection = True            
            self.broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT))

    def onSentKeysError(self, errorNode, keysEntity):
        logger.info("Sent keys were not accepted")        

    def adjustArray(self, arr):
        return HexUtil.decodeHex(binascii.hexlify(arr))
    
    def adjustId(self, _id,byte_count=3):
        _id = format(_id, 'x')
        zfiller = len(_id) if len(_id) % 2 == 0 else len(_id) + 1
        _id = _id.zfill(zfiller if zfiller > byte_count*2 else byte_count*2)
        return binascii.unhexlify(_id)
