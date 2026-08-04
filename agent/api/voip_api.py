"""
VoIP Call API — REST endpoints for browser-based call control.

POST   /api/calls/start       — start outgoing call
POST   /api/calls/{id}/accept — accept incoming call
POST   /api/calls/{id}/end    — end call
POST   /api/calls/{id}/webrtc — WebRTC SDP exchange
GET    /api/calls/events      — SSE stream for call events
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Body, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from voip.voip_adapter import get_voip_adapter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/calls", tags=["calls"])


# ── Models ────────────────────────────────────────────────────


class StartCallRequest(BaseModel):
    phone: str
    bot_id: str


class AcceptCallRequest(BaseModel):
    bot_id: str


class EndCallRequest(BaseModel):
    bot_id: str


class WebRtcRequest(BaseModel):
    bot_id: str
    sdp: str


# ── Routes ─────────────────────────────────────────────────────


@router.post("/start")
async def start_call(req: StartCallRequest):
    """
    Initiate an outgoing VoIP call.

    Request:  {"phone": "1234567890", "bot_id": "233541115312"}
    Response: {"call_id": "...", "state": "ringing"}
    """
    adapter = get_voip_adapter()
    # Construct peer JID from phone number
    peer_jid = f"{req.phone}@s.whatsapp.net"
    result = await adapter.start_call(req.bot_id, peer_jid)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{call_id}/accept")
async def accept_call(call_id: str, req: AcceptCallRequest = Body(...)):
    """
    Accept an incoming VoIP call.

    Request:  {"bot_id": "233541115312"}
    Response: {"call_id": "...", "state": "connecting"}
    """
    adapter = get_voip_adapter()
    result = await adapter.accept_call(req.bot_id, call_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{call_id}/end")
async def end_call(call_id: str, req: EndCallRequest = Body(...)):
    """
    End a VoIP call.

    Request:  {"bot_id": "233541115312"}
    Response: {"call_id": "...", "state": "ended"}
    """
    adapter = get_voip_adapter()
    result = await adapter.end_call(req.bot_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{call_id}/webrtc")
async def webrtc_offer(call_id: str, req: WebRtcRequest = Body(...)):
    """
    Exchange WebRTC SDP offer/answer for browser audio.

    Request:  {"bot_id": "233541115312", "sdp": "<SDP offer>"}
    Response: {"sdp": "<SDP answer>", "call_id": "..."}
    """
    adapter = get_voip_adapter()
    result = await adapter.attach_bridge(req.bot_id, req.sdp)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/events")
async def call_events(request: Request):
    """
    Server-Sent Events stream for VoIP call events.

    Events: state_change, incoming, ended
    """
    adapter = get_voip_adapter()
    queue: asyncio.Queue = asyncio.Queue()

    def on_event(event_type: str, data: dict):
        try:
            queue.put_nowait({"event": event_type, "data": data})
        except asyncio.QueueFull:
            pass

    adapter.add_listener(on_event)

    async def event_generator():
        try:
            yield "event: connected\ndata: {}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    event_type = msg["event"]
                    import json
                    data_str = json.dumps(msg["data"])
                    yield f"event: {event_type}\ndata: {data_str}\n\n"
                except asyncio.TimeoutError:
                    yield ":\n\n"  # Keepalive comment
        finally:
            adapter.remove_listener(on_event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
