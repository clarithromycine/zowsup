"""msg.edit command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd import contact
from app.zowbot_cmd.base import BotCommand
from axolotl import exceptions
from core.axolotl.exceptions import UntrustedIdentityException
from core.common.tools import Jid
import time,os
from core.layers.axolotl.props import PROP_IDENTITY_AUTOTRUST
from core.layers.axolotl.protocolentities.iq_key_get import GetKeysIqProtocolEntity
from core.layers.axolotl.protocolentities.iq_keys_get_result import ResultGetKeysIqProtocolEntity
from core.layers.protocol_calls.protocolentities.call_offer import OfferCallProtocolEntity
from core.layers.protocol_calls.protocolentities.attributes.attributes_call_meta import CallMetaAttributes
from proto import e2e_pb2


logger = logging.getLogger(__name__)


class Cmd_Call_Offer(BotCommand):

    COMMAND = "call.offer"
    DESCRIPTION = "Offer a call to a user"

    async def assureSession(self,lid):

        db = self.bot.botLayer.db

        if not db.session_exists(lid):
            #创建session
            self.bot.idType
            getKeysEntity = GetKeysIqProtocolEntity(
                [lid],
                _id=self.bot.idType
            )
            resultEntity = await self.send_iq_expect(getKeysEntity,ResultGetKeysIqProtocolEntity)
                                    
            resultJids = resultEntity.getJids()                   
            successJids = []
            errorJids = resultEntity.getErrors() #jid -> exception

            for jid in getKeysEntity.jids:
          
                if jid not in resultJids:
                    self.skipEncJids.append(jid)
                    continue
                username = jid.split('@')[0]
                preKeyBundle = resultEntity.getPreKeyBundleFor(jid)
                try:               
                    db.create_session(username, preKeyBundle,
                                                autotrust=self.bot.botLayer.getProp(PROP_IDENTITY_AUTOTRUST, False))
                    successJids.append(jid)
                    return True
                except UntrustedIdentityException as e:
                        errorJids[jid] = e
                        logger.error(e)
                        logger.warning("Ignoring message with untrusted identity")            
        else:
            return True 

        if not db.session_exists(lid):
            return False

    async def execute(self, params, options):

        db = self.bot.botLayer.db

        lid = Jid.normalize(params[0])
        contact = db._store.getContact(lid)
        if contact is None:
            return self.fail(f"Contact {params[0]} not found in database. Please addthe contact first(e.g., using the 'contact.sync' command).")
        
        if not await self.assureSession(contact["lid"]):
            return self.fail(f"Failed to establish session with contact {params[0]}. Cannot offer call.")

                                  
        desttinationJids = [contact["lid"]]
        
        callKey =  os.urandom(32)     
        callEntity = OfferCallProtocolEntity(            
            callCreator=self.bot.profile.config.lid,            
            privacy = "auto",                   
            destinationJids = desttinationJids,            
            callKey = callKey,
            callMetaAttributes=CallMetaAttributes(
                id=self.bot.idType,
                recipient=contact["lid"],                                
            ),
            db = self.bot.botLayer.db,            
        )
        
        await self.bot.botLayer.toLower(callEntity)
        return self.success(
            callId=callEntity.getCallId()
        )


