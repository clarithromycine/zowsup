"""account.getname command module"""
from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities.business.iq_get_business_name import GetBusinessNameIqProtocolEntity
from core.common.tools import Jid
import base64
from core.layers.protocol_iq.protocolentities.business.iq_get_business_name import GetBusinessNameResultIqProtocolEntity
logger = logging.getLogger(__name__)



class Cmd_Account_Getname(BotCommand):

    COMMAND = "account.getname"
    DESCRIPTION = "Get self name"
    async def execute(self,params, options):
        """Execute account.getname command"""
        bot = self.bot
        
        if bot.env.deviceEnv.getOSName() in ["SMBA", "SMB iOS"]:
            result = await self.getBusinessName([Jid.normalize(bot.botId)], options)
            return result
        else:
            value = bot.profile.config.pushname
            return {
                "name": value,
                "type": "individual"
            }

    async def getBusinessName(self,params,options):

        raw = options.get("raw") is not None

        try:            
            entity = GetBusinessNameIqProtocolEntity(jid=Jid.normalize(params[0]))
            result = await self.send_iq_expect(entity, GetBusinessNameResultIqProtocolEntity)

            return self.success(
                name=result.name,
                type="business",
                b64Raw = base64.b64encode(result.rawVNC).decode() if raw else None
            )


        except Exception as e:
            logger.error(f"getBusinessName error for target {params[0]}: {e}")
            return self.fail(error=str(e))
  