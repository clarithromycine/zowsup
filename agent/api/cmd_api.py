"""Command execution API.

POST /api/bot/cmd  — execute a command on a running bot
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from agent.manager.bot_manager import bot_manager
from agent.schemas import BotCmdRequest, CmdResult

logger = logging.getLogger(__name__)

router = APIRouter(tags=["cmd"])


@router.post("/api/bot/cmd", response_model=CmdResult, response_model_exclude_none=True)
async def execute_cmd(req: BotCmdRequest):
    # Check bot exists before attempting execution
    info = bot_manager.get_bot(req.bot_id)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Bot '{req.bot_id}' not found")

    try:
        result, error = await asyncio.to_thread(
            bot_manager.execute_cmd,
            bot_id=req.bot_id,
            cmd_name=req.command,
            args=req.args,
            options=req.options,
            timeout=req.timeout,
        )
    except Exception as e:
        logger.error(f"Command execution failed for bot '{req.bot_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    if error:
        return CmdResult(
            retcode=error.get("code", -1),
            error=error.get("msg", "unknown error"),
        )

    return CmdResult(retcode=0, result=result)
