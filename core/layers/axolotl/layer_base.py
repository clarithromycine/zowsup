from ...layers import YowProtocolLayer
from typing import Optional, Any, List, Dict, Union
from ...layers.axolotl.protocolentities import *
from ...layers.network.layer import YowNetworkLayer
from ...layers import EventCallback
from ...profile.profile import YowProfile

from ...axolotl import exceptions
from ...layers.axolotl.props import PROP_IDENTITY_AUTOTRUST

import inspect
import logging
logger = logging.getLogger(__name__)


class AxolotlBaseLayer(YowProtocolLayer):
    def __init__(self) -> None:
        super().__init__()
        self._manager = None  # type: AxolotlManager | None
        self.skipEncJids = []

    async def send(self, node) -> Any:
        pass

    async def receive(self, node) -> Any:
        await self.processIqRegistry(node)

    @property
    def manager(self) -> Any:
        """
        :return:
        :rtype: AxolotlManager
        """
        return self._manager

    @EventCallback(YowNetworkLayer.EVENT_STATE_CONNECTED)
    def on_connected(self, yowLayerEvent) -> Any:        
        profile = self.getProp("profile")  # type: YowProfile
        if profile is not None:
            self._manager = profile.axolotl_manager

    @EventCallback(YowNetworkLayer.EVENT_STATE_DISCONNECTED)
    def on_disconnected(self, yowLayerEvent) -> Any:
        self._manager = None
        

    async def getKeysFor(self, targets, resultClbk, errorClbk = None, reason=None) -> Any:
        logger.debug(f"getKeysFor(targets={targets}, resultClbk=[omitted], errorClbk=[omitted], reason={reason})")
        async def onSuccess(resultNode, getKeysEntity):                    
            entity = ResultGetKeysIqProtocolEntity.fromProtocolTreeNode(resultNode)
                        
            resultJids = entity.getJids()                   
            successJids = []
            errorJids = entity.getErrors() #jid -> exception
            for jid in getKeysEntity.jids:
          
                if jid not in resultJids:
                    self.skipEncJids.append(jid)
                    continue
                username = jid.split('@')[0]
                preKeyBundle = entity.getPreKeyBundleFor(jid)
                try:               
                    self.manager.create_session(username, preKeyBundle,
                                                autotrust=self.getProp(PROP_IDENTITY_AUTOTRUST, False))
                    successJids.append(jid)
                except exceptions.UntrustedIdentityException as e:
                        errorJids[jid] = e
                        logger.error(e)
                        logger.warning("Ignoring message with untrusted identity")

            result = resultClbk(successJids, errorJids)
            if inspect.isawaitable(result):
                await result

        async def onError(errorNode, getKeysEntity):
            logger.error("ERROR ON GETKEY")
            if errorClbk:
                result = errorClbk(errorNode, getKeysEntity)
                if inspect.isawaitable(result):
                    await result

        idType = self.getProp("ID_TYPE")
        entity = GetKeysIqProtocolEntity(targets, reason=reason,_id=idType)
        await self._sendIq(entity, onSuccess, onError=onError)
