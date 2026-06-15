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

    # Send via msg.send
    try:
        result, error = await asyncio.to_thread(
            bot_manager.execute_cmd,
            bot_id=bot_id,
            cmd_name="msg.send",
            args=[jid, req.content],
            timeout=30,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if error:
        raise HTTPException(status_code=500, detail=error.get("msg", "send failed"))

    # Record outgoing message
    msg_id = result if isinstance(result, str) and result != "JUSTWAIT" else None
    row = conv_store.record_message(
        conv_id=resolved,
        bot_id=bot_id,
        jid=jid,
        direction="outgoing",
        content_type=req.content_type,
        content=req.content,
        msg_id=msg_id,
        status="EXECUTED",
    )
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
