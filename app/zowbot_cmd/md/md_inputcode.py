"""md.inputcode command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import MultiDevicePairPrimaryHelloIqProtocolEntity,MultiDevicePairDeviceResultIqProtocolEntity
from core.common.tools import WATools
from common.utils import Utils
from core.layers.protocol_iq.protocolentities.iq_result import ResultIqProtocolEntity

logger = logging.getLogger(__name__)



class Cmd_Md_InputCode(BotCommand):
    
    COMMAND = "md.inputcode"
    DESCRIPTION = "Input pairing code"


    async def execute(self, params, options):

        bot = self.bot

        if bot.botLayer.pairingStatus != "WAIT_PAIRINGCODE":
            logger.warning(f"Received pairing code input while not waiting for it. Current status: {bot.botLayer.pairingStatus}")
            return
        
        bot.botLayer.pairingCode = params[0]
        if bot.botLayer.pairingCode:
            linkCode = bot.botLayer.pairingCode
            primaryEphemerKeyPair = WATools.generateKeyPair()
            companionEphemerPub = Utils.link_code_decrypt(
                linkCode, bot.botLayer.companionHelloEntity.linkCodePairingWrappedCompanionEphemeralPub
            )
            bot.botLayer.setProp("companionEphemerPub", companionEphemerPub)
            bot.botLayer.setProp("companionAuthKeyPub", bot.botLayer.companionHelloEntity.companionServerAuthKeyPub)
            bot.botLayer.setProp("keypair", primaryEphemerKeyPair)
            linkCodePairingWrappedPrimaryEphemeralPub = Utils.link_code_encrypt(
                linkCode, primaryEphemerKeyPair.public.data
            )
            # Send primary_hello response

            try :
                entity = MultiDevicePairPrimaryHelloIqProtocolEntity(
                    linkCodePairingWrappedPrimaryEphemeralPub=linkCodePairingWrappedPrimaryEphemeralPub,
                    primaryIdentityPub=bot.botLayer.db.identity.publicKey.serialize()[1:],
                    linkCodePairingRef=bot.botLayer.companionHelloEntity.linkCodePairingRef
                )            
                result = await self.send_iq_expect(entity, ResultIqProtocolEntity)
                return self.success()
                        
            except Exception as e:
                logger.error(f"Error during pairing process: {e}")
                return self.fail(error=str(e))


