"""Send message API — high-level wrapper over msg.send / msg.sendad / msg.sendmedia."""

from __future__ import annotations

import asyncio
import base64
import logging
import tempfile
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from agent.manager.bot_manager import bot_manager
from agent.schemas import SendMsgRequest, CmdResult

logger = logging.getLogger(__name__)
router = APIRouter(tags=["msg"])

# Valid media types for msg.sendmedia
_VALID_MEDIA_TYPES = {"image", "video", "audio", "document"}


@router.post("/api/sendmsg", response_model=CmdResult)
async def send_message(req: SendMsgRequest):
    """Send a text, ad, or media message."""

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
        options = {"title": ad.title, "url": ad.url, "body": ad.body or "",
                   "thumbnailb64": ad.thumbnailb64, "waitid": req.waitid}

    # ── Media message ──
    elif content.media is not None:
        media = content.media

        if media.type not in _VALID_MEDIA_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid media type '{media.type}'. Must be: {', '.join(sorted(_VALID_MEDIA_TYPES))}"
            )

        file_path = _resolve_media_path(media)
        if not file_path:
            raise HTTPException(status_code=422, detail="media must have 'url', 'base64', or 'path'")

        command = "msg.sendmedia"
        args = [req.to, media.type, file_path]
        options: dict = {}
        if media.caption:
            options["caption"] = media.caption
        if media.fileName:
            options["fileName"] = media.fileName
        if req.waitid:
            options["waitMsgId"] = req.waitid

        # Track temp file for cleanup after command completes
        _temp_file = file_path if media.base64 else None

        try:
            return await _execute(command, req, args, options)
        finally:
            if _temp_file and os.path.exists(_temp_file):
                try:
                    os.unlink(_temp_file)
                except OSError:
                    pass

    else:
        raise HTTPException(status_code=422, detail="content must have 'text', 'ad', or 'media' field")

    return await _execute(command, req, args, options)


async def _execute(command: str, req: SendMsgRequest, args: list, options: dict) -> CmdResult:
    """Execute a bot command and return a CmdResult."""
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
        return CmdResult(retcode=error.get("code", -1), error=error.get("msg", "unknown error"))
    return CmdResult(retcode=0, result=result)


def _resolve_media_path(media) -> str | None:
    """Resolve media content to a file path or URL string.

    Returns None if no valid source is provided.
    """
    # URL — pass through directly (msg.sendmedia handles HTTP URLs)
    if media.url:
        return media.url

    # Base64 — decode to temp file
    if media.base64:
        data = base64.b64decode(media.base64)
        suffix = _ext_to_suffix(media.type, media.fileName)
        fd, path = tempfile.mkstemp(suffix=suffix, prefix="zowsup_media_")
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        return path

    # Server-side path
    if media.path:
        return media.path

    return None


def _ext_to_suffix(media_type: str, file_name: str | None) -> str:
    """Guess file extension from media type."""
    ext_map = {"image": ".jpg", "video": ".mp4", "audio": ".ogg", "document": ""}
    if file_name:
        return Path(file_name).suffix or ext_map.get(media_type, ".bin")
    return ext_map.get(media_type, ".bin")
