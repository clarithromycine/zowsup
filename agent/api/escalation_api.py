"""Escalation API — human operator console for escalated conversations.

GET    /api/escalation?status=pending&bot_id=   — list escalations
GET    /api/escalation/{id}                     — detail
POST   /api/escalation/{id}/claim               — claim for operator
POST   /api/escalation/{id}/unclaim             — return to queue
POST   /api/escalation/{id}/resolve             — resolve
POST   /api/escalation/{id}/reply               — send message to conversation
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Body

from agent.manager.bot_manager import bot_manager
from agent.manager.conversation_store import conv_store
from agent.manager.escalation_queue import escalation_queue

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/escalation", tags=["escalation"])


# ── List ─────────────────────────────────────────────────────────────────────

@router.get("")
async def list_escalations(
    status: str | None = None,
    bot_id: str | None = None,
):
    """List escalations.  Default: all non-resolved."""
    items = escalation_queue.list(status=status, bot_id=bot_id)
    # Enrich with conversation info
    result = []
    for item in items:
        conv = conv_store.get_conversation(item["conversation_id"])
        result.append({
            **item,
            "conversation": conv,
        })
    return result


# ── Detail ───────────────────────────────────────────────────────────────────

@router.get("/{esc_id}")
async def get_escalation(esc_id: str):
    esc = escalation_queue.get(esc_id)
    if esc is None:
        raise HTTPException(status_code=404, detail=f"Escalation {esc_id} not found")
    conv = conv_store.get_conversation(esc["conversation_id"])
    messages = conv_store.get_messages(esc["conversation_id"], limit=50) if conv else []
    return {**esc, "conversation": conv, "messages": messages}


# ── Create ───────────────────────────────────────────────────────────────────

@router.post("")
async def create_escalation(
    bot_id: str = Body(...),
    conversation_id: str = Body(...),
    reason: str = Body("manual"),
    priority: str = Body("normal"),
    agent_id: str = Body(""),
    id: str = Body(""),
    escalation_note: str = Body(""),
):
    """Create an escalation (standalone mode)."""
    import uuid
    esc_id = id or str(uuid.uuid4())
    conv = conv_store.get_conversation(conversation_id)
    esc = escalation_queue.add(
        bot_id=bot_id,
        conversation_id=conversation_id,
        reason=reason,
        priority=priority,
        agent_id=agent_id,
        escalation_id=esc_id,
        escalation_note=escalation_note,
    )

    # Insert system note with escalation context
    parts = conversation_id.split(":", 1)
    bid = parts[0] if len(parts) > 1 else ""
    jid = parts[1] if len(parts) > 1 else ""
    conv_store.record_message(
        conv_id=conversation_id, bot_id=bid, jid=jid,
        direction="note", content_type="SYSTEM",
        content="⬆ Escalation created",
        note=escalation_note.strip() if escalation_note.strip() else None,
        note_type="escalation_reason",
    )

    return {**esc, "conversation": conv}


# ── Claim ────────────────────────────────────────────────────────────────────

@router.post("/{esc_id}/claim")
async def claim_escalation(esc_id: str, operator: str = Body(..., embed=True)):
    if not escalation_queue.claim(esc_id, operator):
        raise HTTPException(status_code=409, detail="Already claimed or not found")
    return {"id": esc_id, "claimed_by": operator, "status": "claimed"}


# ── Unclaim ──────────────────────────────────────────────────────────────────

@router.post("/{esc_id}/unclaim")
async def unclaim_escalation(esc_id: str):
    if not escalation_queue.unclaim(esc_id):
        raise HTTPException(status_code=409, detail="Not claimed or not found")
    return {"id": esc_id, "status": "pending"}


# ── Resolve ──────────────────────────────────────────────────────────────────

@router.post("/{esc_id}/resolve")
async def resolve_escalation(esc_id: str, resolution_note: str = Body("", embed=True)):
    if not escalation_queue.resolve(esc_id, resolution_note=resolution_note):
        raise HTTPException(status_code=404, detail=f"Escalation {esc_id} not found")

    # Insert system note into the conversation
    esc = escalation_queue.get(esc_id)
    if esc:
        conv_id = esc["conversation_id"]
        parts = conv_id.split(":", 1)
        bot_id = parts[0] if len(parts) > 1 else ""
        jid = parts[1] if len(parts) > 1 else ""
        conv_store.record_message(
            conv_id=conv_id, bot_id=bot_id, jid=jid,
            direction="note", content_type="SYSTEM",
            content="✅ Escalation resolved",
            note=resolution_note.strip() if resolution_note.strip() else None,
            note_type="escalation_resolution",
        )

    return {"id": esc_id, "status": "resolved"}


# ── Reply ────────────────────────────────────────────────────────────────────

@router.post("/{esc_id}/reply")
async def reply_to_escalation(esc_id: str, text: str = Body(..., embed=True)):
    """Send a reply to the escalated conversation via the bot."""
    esc = escalation_queue.get(esc_id)
    if esc is None:
        raise HTTPException(status_code=404, detail=f"Escalation {esc_id} not found")

    conv_id = esc["conversation_id"]
    parts = conv_id.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail=f"Invalid conversation id: {conv_id}")
    bot_id, jid = parts

    if bot_manager.get_bot_instance(bot_id) is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not running")

    try:
        result, error = await asyncio.to_thread(
            bot_manager.execute_cmd,
            bot_id=bot_id,
            cmd_name="msg.send",
            args=[jid, text],
            options={"waitid": 15},
            timeout=30,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if error:
        raise HTTPException(status_code=500, detail=error.get("msg", "send failed"))

    # Record in conversation store
    msg_id = result if isinstance(result, str) and result not in ("JUSTWAIT", "TIMEOUT") else None
    from agent.manager.conversation_store import conv_store
    conv_store.record_message(
        conv_id=conv_id, bot_id=bot_id, jid=jid,
        direction="outgoing", content_type="TEXT",
        content=text, msg_id=msg_id, status="EXECUTED",
    )

    return {"sent": True, "conversation_id": conv_id, "text": text}
