"""account.setavatar command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
import io
import requests
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_profiles.protocolentities import SetPictureIqProtocolEntity
from core.common.optionalmodules import PILOptionalModule
from app.param_not_enough_exception import ParamsNotEnoughException
from core.layers.protocol_profiles.protocolentities import ResultSetPictureIqProtocolEntity

logger = logging.getLogger(__name__)



class Cmd_Account_SetAvatar(BotCommand):
    
    COMMAND = "account.setavatar"
    DESCRIPTION = "Set account avatar"


    async def execute(self, params, options):

        if len(params) == 0:
            raise ParamsNotEnoughException()
        
        url = params[0]
        
        try:
            with PILOptionalModule(failMessage="No PIL library installed, try install pillow") as imp:
                Image = imp("Image")
                src = Image.open(io.BytesIO(requests.get(url).content)).convert("RGB")
                picture = io.BytesIO()
                preview = io.BytesIO()
                src.resize((640, 640)).save(picture, format="jpeg")
                src.resize((96, 96)).save(preview, format="jpeg")
                entity = SetPictureIqProtocolEntity("s.whatsapp.net", preview.getvalue(), picture.getvalue())
                result = await self.send_iq_expect(entity, ResultSetPictureIqProtocolEntity)
                return self.success(
                    pictureId=result.pictureId
                )
        except Exception as e:
            logger.error(f"setAvatar error: {e}")
            return self.fail(error=str(e))

