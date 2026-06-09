


from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging

from app.zowbot_cmd.base import BotCommand

logger = logging.getLogger(__name__)
    
class BotSendCommand(BotCommand):

    async def assureContactsAndSend(self, params, options, send_func, redo_func):
        """Delegate to ContactManager via botLayer facade (single source of truth)."""
        return await self.bot.botLayer.assureContactsAndSend(
            params, options, send_func, redo_func
        )
     
