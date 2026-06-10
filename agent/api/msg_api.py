"""Send message API — high-level wrapper over msg.send / msg.sendad."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from agent.manager.bot_manager import bot_manager
from agent.schemas import SendMsgRequest, CmdResult

logger = logging.getLogger(__name__)
router = APIRouter(tags=["msg"])


@router.post("/api/sendmsg", response_model=CmdResult)
async def send_message(req: SendMsgRequest):
    """Send a text or ad message. Maps to msg.send or msg.sendad internally."""

    content = req.content

    # ── Text message ──
    if content.text is not None:
        command = "msg.send"
        args = [req.to, content.text]
        options: dict = {"waitid": req.waitid} if req.waitid else {}

    # ── Ad message ──
    elif content.ad is not None:
        ad = content.ad
        command = "msg.sendad"
        args = [req.to, ad.text]
        options = {"title": ad.title, "url": ad.url,"body": ad.body or "","thumbnailb64": ad.thumbnailb64,"waitid": req.waitid}

    else:
        raise HTTPException(status_code=422, detail="content must have 'text' or 'ad' field")

    # Check bot exists
    if bot_manager.get_bot(req.bot_id) is None:
        raise HTTPException(status_code=404, detail=f"Bot '{req.bot_id}' not found")

    try:
        result, error = await asyncio.to_thread(
            bot_manager.execute_cmd,
            bot_id=req.bot_id,
            cmd_name=command,
            args=args,
            options=options,
            timeout=30,
        )
    except Exception as e:
        logger.error(f"Send message failed for bot '{req.bot_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    if error:
        return CmdResult(
            retcode=error.get("code", -1),
            error=error.get("msg", "unknown error"),
        )

    return CmdResult(retcode=0, result=result)
