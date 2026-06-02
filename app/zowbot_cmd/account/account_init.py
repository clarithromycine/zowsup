"""account.init command module with full implementation extraction"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
from core.layers.protocol_iq.protocolentities import PushGetIqProtocolEntity, PropsIqProtocolEntity

logger = logging.getLogger(__name__)

COMMAND = "account.init"
DESCRIPTION = "Initialize account"


async def execute(bot, params, options):
    """
    Initialize account configuration by sending push and props IQ entities.
    
    Returns: JUSTWAIT
    
    Previous location: ZowBotLayer.getConfig()
    """
    try:
        push = PushGetIqProtocolEntity()
        logger.info("push iq")
        await bot.botLayer._sendIqAsync(push)                
        logger.info("props iq")
        props = PropsIqProtocolEntity()
        await bot.botLayer._sendIqAsync(props)
    except Exception as e:
        logger.error(f"getConfig error: {e}")
        raise
    
    return "JUSTWAIT"
