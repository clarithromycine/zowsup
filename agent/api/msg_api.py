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


@router.post("/api/sendmsg", response_model=CmdResult, response_model_exclude_none=True)
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

    original_text = args[1] if command == "msg.send" and len(args) >= 2 else ""
    translated_text = None
    target_lang = ""
    if command == "msg.send" and len(args) >= 2:
        from agent.plugin import MessageContext
        from agent.plugin.manager import plugin_manager
        ctx = MessageContext(bot_id=req.bot_id, jid=args[0], direction="outgoing", content_type="TEXT", content=args[1], conversation_id=f"{req.bot_id}:{args[0]}")
        actions = await plugin_manager.dispatch_on_before_send(ctx)
        for a in actions:
            if hasattr(a, "text"):
                translated_text = a.text
                target_lang = getattr(a, "target_lang", "")
                args[1] = a.text
                break

    try:
        # Ensure waitid for msg.send so we get the real WhatsApp msg_id back
        if command == "msg.send" and "waitid" not in options:
            options = dict(options)
            options["waitid"] = 15
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

    if translated_text and translated_text != original_text:
        from agent.manager.conversation_store import conv_store
        from agent.manager.log_broadcaster import log_broadcaster
        conv_id = f"{req.bot_id}:{req.to}"
        # Store outgoing with translated text
        out_id = result if isinstance(result, str) and result not in ("JUSTWAIT", "TIMEOUT") else None
        out_row = conv_store.record_message(conv_id=conv_id, bot_id=req.bot_id, jid=req.to, direction="outgoing", content_type="TEXT", content=f"[{target_lang}] {translated_text}" if target_lang else translated_text, msg_id=out_id, status="EXECUTED")
        # Store original as note, linked to parent
        note = conv_store.record_message(conv_id=conv_id, bot_id=req.bot_id, jid=req.to, direction="note", content_type="ORIGINAL", content=original_text, status="")
    else:
        _record_outgoing(req.bot_id, req.to, result, req.content)
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

def _record_outgoing(bot_id: str, to_jid: str, result, content) -> None:
    """Record an outgoing message in the conversation store."""
    try:
        from agent.manager.conversation_store import conv_store

        # Resolve to canonical LID-based conversation if one exists
        resolved = conv_store.resolve_conversation_jid(bot_id, to_jid)
        if resolved:
            parts = resolved.split(":", 1)
            canonical_jid = parts[1] if len(parts) > 1 else to_jid
            conv_id = resolved
        else:
            canonical_jid = to_jid
            conv_id = f"{bot_id}:{to_jid}"

        text = content.text if content.text else ""
        ctype = "TEXT"
        if content.ad is not None:
            text = content.ad.text or ""
            ctype = "AD"
        elif content.media is not None:
            text = content.media.caption or f"[{content.media.type}]"
            ctype = content.media.type.upper()

        # Determine pn_jid: set when canonical_jid is a phone number
        _pn = canonical_jid if canonical_jid.endswith("@s.whatsapp.net") else None

        msg_id = result if isinstance(result, str) and result not in ("JUSTWAIT", "TIMEOUT") else None
        conv_store.record_message(
            conv_id=conv_id, bot_id=bot_id, jid=canonical_jid,
            direction="outgoing", content_type=ctype, content=text,
            msg_id=msg_id, status="EXECUTED", pn_jid=_pn,
        )
    except Exception:
        pass
