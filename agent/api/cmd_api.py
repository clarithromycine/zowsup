"""
Command execution API.

POST /api/bots/{bot_id}/cmd  — execute a command on a running bot (sync wait)
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from agent.manager.bot_manager import bot_manager
from agent.schemas import BotCmdRequest, CmdResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bots", tags=["commands"])


@router.post("/{bot_id}/cmd", response_model=CmdResult)
async def execute_cmd(bot_id: str, req: BotCmdRequest):
    """Execute a command on a running bot and return the result.

    The request blocks until the command completes or the timeout is reached.
    Uses asyncio.to_thread() to avoid blocking the FastAPI event loop.
    """
    # Check bot exists before attempting execution
    info = bot_manager.get_bot(bot_id)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found")

    try:
        # callDirectCompat is blocking — run in thread pool
        result, error = await asyncio.to_thread(
            bot_manager.execute_cmd,
            bot_id=bot_id,
            cmd_name=req.command,
            args=req.args,
            options=req.options,
            timeout=req.timeout,
        )
    except Exception as e:
        logger.error(f"Command execution failed for bot '{bot_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    if error:
        return CmdResult(
            retcode=error.get("code", -1),
            error=error.get("msg", "unknown error"),
        )

    return CmdResult(retcode=0, result=result)

