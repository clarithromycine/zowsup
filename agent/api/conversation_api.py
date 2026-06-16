"""Conversation CRUD API.

GET    /api/conversation?bot_id=...           — list conversations
GET    /api/conversation/{conv_id:path}        — detail + messages
DELETE /api/conversation/{conv_id:path}        — delete or close
POST   /api/conversation/{conv_id:path}/message       — send message
POST   /api/conversation/{conv_id:path}/message/{id}/revoke — revoke message

conv_id format: bot_id:lid (canonical).  bot_id:pn_jid also resolves transparently.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query

from agent.manager.bot_manager import bot_manager
from agent.manager.conversation_store import conv_store
from agent.schemas import (
    ConversationInfo, ConversationDetail, MessageInfo, SendMessageRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["conversations"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_conv_id(raw_conv_id: str) -> str | None:
    """Resolve a raw conv_id (bot_id:query_jid) to the canonical conv_id.

    If query_jid is a PN (phone@s.whatsapp.net), resolve to the LID-based
    conversation.  Otherwise return the raw conv_id as-is.
    """
    parts = raw_conv_id.split(":", 1)
    if len(parts) != 2:
        return None
    bot_id, query_jid = parts
    resolved = conv_store.resolve_conversation_jid(bot_id, query_jid)
    return resolved  # may be None


# ── List ─────────────────────────────────────────────────────────────────────

@router.get("/api/conversation", response_model=list[ConversationInfo])
async def list_conversations(
    bot_id: str | None = Query(None, description="Filter by bot ID"),
):
    rows = conv_store.list_conversations(bot_id)
    return [ConversationInfo(**r) for r in rows]


# ── Media Download (must be before Detail — :path is greedy) ────────────────

@router.get("/api/conversation/{conv_id:path}/message/{msg_id:int}/media")
async def download_media(conv_id: str, msg_id: int):
    """Download and decrypt media (IMAGE/VIDEO/AUDIO/DOCUMENT) for a message.

    Returns the media file with the correct Content-Type.
    First access: downloads + decrypts + caches locally.
    Subsequent accesses: serves from local cache (instant).
    """
    from fastapi.responses import Response, FileResponse
    import base64 as _b64
    from pathlib import Path

    resolved = _resolve_conv_id(conv_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found")

    # Find the message
    target = None
    for m in conv_store.get_messages(resolved, limit=1000):
        if m["id"] == msg_id:
            target = m
            break
    if target is None:
        raise HTTPException(status_code=404, detail=f"Message {msg_id} not found")

    media_url = target.get("media_url")
    media_key_b64 = target.get("media_key")
    media_mimetype = target.get("media_mimetype") or "application/octet-stream"
    content_type_str = target.get("content_type", "")

    if not media_url or not media_key_b64:
        raise HTTPException(status_code=404,
                            detail=f"Message {msg_id} has no media "
                                   f"(url={'yes' if media_url else 'no'}, "
                                   f"key={'yes' if media_key_b64 else 'no'})")

    # ── Cache check ──
    from conf.constants import SysVar
    parts = resolved.split(":", 1)
    bot_id = parts[0]
    wa_msg_id = target.get("msg_id") or f"msg{msg_id}"
    dl_root = getattr(SysVar, 'DOWNLOAD_PATH', '') or 'data/download'
    cache_root = Path(dl_root) / "media_cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_dir = cache_root / bot_id
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{wa_msg_id}_{content_type_str.lower()}"
    if cache_file.exists():
        return FileResponse(str(cache_file), media_type=media_mimetype)

    # ── Download encrypted file from WhatsApp CDN ──
    import requests as _requests
    try:
        enc_data = _requests.get(media_url, timeout=30).content
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Media download failed: {e}")

    if not enc_data:
        raise HTTPException(status_code=502, detail="Empty media response")

    # ── Decrypt ──
    from core.layers.protocol_media.mediacipher import MediaCipher
    media_key = _b64.b64decode(media_key_b64)

    if content_type_str == "VIDEO":
        media_info = MediaCipher.INFO_VIDEO
    elif content_type_str == "AUDIO":
        media_info = MediaCipher.INFO_AUDIO
    elif content_type_str == "DOCUMENT":
        media_info = MediaCipher.INFO_DOCUMENT
    else:
        media_info = MediaCipher.INFO_IMAGE

    try:
        filedata = MediaCipher().decrypt(enc_data, media_key, media_info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Media decryption failed: {e}")

    if filedata is None:
        raise HTTPException(status_code=500, detail="Media decryption produced no data")

    # ── Cache to disk ──
    try:
        cache_file.write_bytes(filedata)
        logger.info(f"Media cached: {cache_file} ({len(filedata)} bytes)")
    except Exception as e:
        logger.warning(f"Media cache write failed ({cache_file}): {e}")

    return Response(content=filedata, media_type=media_mimetype)


# ── Detail ───────────────────────────────────────────────────────────────────

@router.get("/api/conversation/{conv_id:path}", response_model=ConversationDetail)
async def get_conversation(
    conv_id: str,
    limit: int = Query(50, ge=1, le=500, description="Max messages"),
    before: float | None = Query(None, description="Only messages before this WhatsApp timestamp"),
    since: float | None = Query(None, description="Only messages after this created_at timestamp (incremental poll)"),
):
    resolved = _resolve_conv_id(conv_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found")

    conv = conv_store.get_conversation(resolved)
    if conv is None:
        raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found")

    messages = conv_store.get_messages(resolved, limit=limit, before=before, since=since)
    return ConversationDetail(
        **conv,
        messages=[MessageInfo(**m) for m in messages],
    )


# ── Delete / Close ───────────────────────────────────────────────────────────

@router.delete("/api/conversation/{conv_id:path}", response_model=dict)
async def delete_conversation(
    conv_id: str,
    mode: str = Query("delete", description="'delete' (hard) or 'close' (soft)"),
):
    resolved = _resolve_conv_id(conv_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found")

    if mode == "close":
        if not conv_store.close_conversation(resolved):
            raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found")
        return {"id": resolved, "closed": True}
    else:
        if not conv_store.delete_conversation(resolved):
            raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found")
        return {"id": resolved, "deleted": True}


# ── Send Message ─────────────────────────────────────────────────────────────

@router.post("/api/conversation/{conv_id:path}/message", response_model=MessageInfo)
async def send_message(conv_id: str, req: SendMessageRequest):
    """Send a message to the conversation's JID via the bot."""
    resolved = _resolve_conv_id(conv_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found")

    parts = resolved.split(":", 1)
    bot_id, jid = parts

    # Verify bot exists and is running
    bot_info = bot_manager.get_bot(bot_id)
    if bot_info is None or bot_manager.get_bot_instance(bot_id) is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found or not running")

    # Allow plugins to transform outgoing content
    original_content = req.content
    content = original_content
    target_lang = ""
    from agent.plugin import MessageContext
    from agent.plugin.manager import plugin_manager
    ctx = MessageContext(bot_id=bot_id, jid=jid, direction="outgoing", content_type=req.content_type, content=content, conversation_id=resolved)
    actions = await plugin_manager.dispatch_on_before_send(ctx)
    for a in actions:
        if hasattr(a, "text"):
            content = a.text
            target_lang = getattr(a, "target_lang", "")
            break

    # Send via msg.send (with waitid to capture the real WhatsApp msg_id)
    try:
        result, error = await asyncio.to_thread(
            bot_manager.execute_cmd,
            bot_id=bot_id,
            cmd_name="msg.send",
            args=[jid, content],
            options={"waitid": 15},
            timeout=30,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if error:
        raise HTTPException(status_code=500, detail=error.get("msg", "send failed"))

    # Record outgoing message (with [lang] prefix if translated)
    display_text = f"[{target_lang}] {content}" if target_lang else content
    msg_id = result if isinstance(result, str) and result not in ("JUSTWAIT", "TIMEOUT") else None
    row = conv_store.record_message(
        conv_id=resolved, bot_id=bot_id, jid=jid,
        direction="outgoing", content_type=req.content_type,
        content=display_text, msg_id=msg_id, status="EXECUTED",
    )

    # If translated, store original directly on the message row
    if content != original_content:
        conv_store.update_message_note(row["id"], original_content, "ORIGINAL")
        row["note"] = original_content

    return MessageInfo(**row)


# ── Revoke ───────────────────────────────────────────────────────────────────

@router.post("/api/conversation/{conv_id:path}/message/{msg_id:int}/revoke", response_model=dict)
async def revoke_message(conv_id: str, msg_id: int):
    """Revoke a WhatsApp message by its DB message id."""
    resolved = _resolve_conv_id(conv_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found")

    # Find message with matching local DB id
    target = None
    for m in conv_store.get_messages(resolved, limit=1000):
        if m["id"] == msg_id:
            target = m
            break

    if target is None:
        raise HTTPException(status_code=404, detail=f"Message {msg_id} not found in conversation")

    wa_msg_id = target.get("msg_id")
    if not wa_msg_id:
        raise HTTPException(status_code=400, detail="Message has no WhatsApp msg_id to revoke")

    parts = resolved.split(":", 1)
    bot_id, jid = parts

    try:
        result, error = await asyncio.to_thread(
            bot_manager.execute_cmd,
            bot_id=bot_id,
            cmd_name="msg.revoke",
            args=[jid, wa_msg_id],
            timeout=15,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if error:
        raise HTTPException(status_code=500, detail=error.get("msg", "revoke failed"))

    conv_store.update_message_status(wa_msg_id, "REVOKE")
    return {"revoked": True, "msg_id": wa_msg_id}
