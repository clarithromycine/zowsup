"""regfcm command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
import asyncio
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import PushSetIqProtocolEntity
from fcm_push_receiver.fcm_module import FcmModule

logger = logging.getLogger(__name__)


class Cmd_Misc_Regfcm(BotCommand):

    COMMAND = "misc.regfcm"
    DESCRIPTION = "Register FCM"

    async def execute(self, params, options):
        bot = self.bot
        profile = bot.botLayer.getStack().getProp("profile")
        fcm = FcmModule(fcmConfig=FcmModule.ANDROID_DEFAULT, isReg=True, profile=profile)
        loop = bot.botLayer.getStack().getLoop()
        fcm.startMessageListener(bot.botLayer.fcmMsgCallback, loop=loop)
        token = fcm.getFcmToken()
        #await asyncio.sleep(2)
        logger.debug("regFcm: sending push set")
        entity = PushSetIqProtocolEntity(id=token)
        await bot.botLayer.toLower(entity)
        return "JUSTWAIT"

