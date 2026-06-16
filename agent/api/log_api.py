"""
Log streaming API endpoints.

GET      /api/bot/{bot_id}/logs/recent  — pull recent N log lines
DELETE   /api/bot/{bot_id}/logs         — clear persisted logs
WebSocket /api/bot/{bot_id}/logs        — real-time log stream
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from agent.manager.log_broadcaster import log_broadcaster
from agent.manager.bot_manager import bot_manager
from agent.schemas import LogLinesResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bot", tags=["logs"])


# ── REST: Recent Logs ────────────────────────────────────────────────────────


@router.get("/{bot_id}/logs/recent", response_model=LogLinesResponse)
async def get_recent_logs(
    bot_id: str,
    lines: int = Query(50, ge=1, le=1000, description="Number of recent lines"),
):
    """Return the most recent N log lines for a bot.

    Requires the bot to have been started (logs are captured from all
    bot threads via the logging handler).
    """
    # Verify bot exists (or has existed)
    info = bot_manager.get_bot(bot_id)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found")

    recent = log_broadcaster.get_recent(bot_id, lines=lines)
    return LogLinesResponse(bot_id=bot_id, lines=recent)


# ── Clear logs ────────────────────────────────────────────────────────────────


@router.delete("/{bot_id}/logs", response_model=dict)
async def clear_logs(bot_id: str):
    """Clear all persisted and in-memory log data for a bot."""
    log_broadcaster.clear_logs(bot_id)
    return {"bot_id": bot_id, "cleared": True}


# ── WebSocket: Real-time Log Stream ──────────────────────────────────────────


@router.websocket("/{bot_id}/logs")
async def ws_bot_logs(
    websocket: WebSocket,
    bot_id: str,
    tail: int = Query(0, ge=0, le=1000, description="Send last N lines on connect"),
    access_key: Optional[str] = Query(None),
):
    """Real-time log stream for a bot.

    On connect, sends the last `tail` lines, then pushes new lines as they arrive.
    Closes with code 4003 if access key is invalid.
    """
    # Auth check
    from agent.server import _check_ws_access_key
    if not await _check_ws_access_key(websocket, access_key):
        await websocket.close(code=4003, reason="Invalid access key")
        return

    await websocket.accept()
    from agent.server import ws_connected
    ws_connected()
    logger.info(f"WebSocket log client connected for bot '{bot_id}' (tail={tail})")

    sub = None
    try:
        # Send history
        if tail > 0:
            history = log_broadcaster.get_recent(bot_id, lines=tail)
            for line in history:
                try:
                    await websocket.send_text(line)
                except WebSocketDisconnect:
                    return

        # Subscribe for real-time updates
        sub = log_broadcaster.subscribe(bot_id)

        async def _read_loop():
            while not log_broadcaster._shutting_down:
                try:
                    line = await sub.queue.get()
                except asyncio.CancelledError:
                    return

                if line is None:
                    return
                try:
                    await websocket.send_text(line)
                except WebSocketDisconnect:
                    return

        async def _close_watcher():
            """Block until client disconnects (receive_text raises on close)."""
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                pass

        read_task = asyncio.ensure_future(_read_loop())
        watch_task = asyncio.ensure_future(_close_watcher())
        done, pending = await asyncio.wait(
            [read_task, watch_task], return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()
        if read_task in pending:
            logger.info(f"WebSocket log client disconnected for bot '{bot_id}'")
    finally:
        from agent.server import ws_disconnected
        ws_disconnected()
        if sub is not None:
            log_broadcaster.unsubscribe(bot_id, sub)


# ── WebSocket: Real-time Event Stream ────────────────────────────────────────


@router.websocket("/{bot_id}/events")
async def ws_bot_events(
    websocket: WebSocket,
    bot_id: str,
    tail: int = Query(0, ge=0, le=200, description="Send last N events on connect"),
    access_key: Optional[str] = Query(None),
):
    """Real-time structured event stream for a bot.

    Pushes JSON events (messages, status changes, command results) as they occur.
    Each message is a JSON object with keys: type, bot_id, timestamp, data.

    Closes with code 4003 if access key is invalid.
    """
    from agent.server import _check_ws_access_key
    if not await _check_ws_access_key(websocket, access_key):
        await websocket.close(code=4003, reason="Invalid access key")
        return

    await websocket.accept()
    from agent.server import ws_connected
    ws_connected()
    logger.info(f"WebSocket event client connected for bot '{bot_id}' (tail={tail})")

    sub = None
    try:
        # Send history
        if tail > 0:
            history = log_broadcaster.get_recent_events(bot_id, count=tail)
            for event in history:
                try:
                    await websocket.send_text(json.dumps(event, ensure_ascii=False, default=str))
                except WebSocketDisconnect:
                    return

        # Subscribe for real-time updates
        sub = log_broadcaster.subscribe_events(bot_id)

        async def _read_loop():
            while not log_broadcaster._shutting_down:
                try:
                    payload = await sub.queue.get()
                except asyncio.CancelledError:
                    return

                if payload is None:  # Sentinel
                    return
                try:
                    await websocket.send_text(payload)
                except WebSocketDisconnect:
                    return

        async def _close_watcher():
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                pass

        read_task = asyncio.ensure_future(_read_loop())
        watch_task = asyncio.ensure_future(_close_watcher())
        done, pending = await asyncio.wait(
            [read_task, watch_task], return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()
        if read_task in pending:
            logger.info(f"WebSocket event client disconnected for bot '{bot_id}'")
    finally:
        from agent.server import ws_disconnected
        ws_disconnected()
        if sub is not None:
            log_broadcaster.unsubscribe_events(bot_id, sub)