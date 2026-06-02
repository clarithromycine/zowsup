"""account.setname command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities.business.iq_set_business_name import SetBusinessNameResultIqProtocolEntity
from core.layers.protocol_presence.protocolentities.presence import PresenceProtocolEntity
from app.param_not_enough_exception import ParamsNotEnoughException
import names,uuid
from core.layers.protocol_iq.protocolentities.business import SetBusinessNameIqProtocolEntity

logger = logging.getLogger(__name__)


class Cmd_Account_SetName(BotCommand):

    COMMAND = "account.setname"
    DESCRIPTION = "Set self name"


    async def execute(self, params, options):    

        if len(params)==0:
            params=[names.get_full_name()]
        self.bot.profile.config.pushname = params[0]
        self.bot.profile.write_config(self.bot.profile.config)                         
        if self.bot.env.deviceEnv.getOSName() in ["SMBA","SMB iOS"]:
            #call the api if business 
            return await self.setBusinessName(params, options)
        else:            
            id = str(uuid.uuid4())

            return self.success(
                name=params[0],
                type="individual"
            )



    async def setBusinessName(self, params, options):     

        try:
            entity = SetBusinessNameIqProtocolEntity(profile = self.bot.profile, name = params[0])
            result = await self.send_iq_expect(entity, SetBusinessNameResultIqProtocolEntity)
            return self.success(
                name=params[0],
                type="business"
            )

        except Exception as e:
            logger.error(f"setBusinessName error for target {params[0]}: {e}")  
            return self.fail(error=str(e))


