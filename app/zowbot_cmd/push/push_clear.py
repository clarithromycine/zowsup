"""account.init command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from app.zowbot_cmd.base import BotCommand
from core.layers.protocol_iq.protocolentities import PushClearIqProtocolEntity, ResultIqProtocolEntity

logger = logging.getLogger(__name__)


'''
<iq to="s.whatsapp.net"
    xmlns="urn:xmpp:whatsapp:push"
    type="set"
    id="{hexString8}">
    <clear fbns="platform:{A0A5}"/>
</iq>
'''
class Cmd_Push_Clear(BotCommand):
    COMMAND = "push.clear"
    DESCRIPTION = "Clear firebase push token"

    async def execute(self, params, options):
        try:
            clear = PushClearIqProtocolEntity("gcm")        
            result = await self.send_iq_expect(clear,ResultIqProtocolEntity)
            return self.success()
        except Exception as e:
            return self.fail(error=str(e))  
                
