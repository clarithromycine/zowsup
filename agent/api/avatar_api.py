"""Avatar API — serve cached contact avatars with lazy download.

GET /api/avatar/{conv_id}  — returns the avatar image (JPEG) for a conversation.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from agent.manager.bot_manager import bot_manager
from agent.manager.conversation_store import conv_store
from conf.constants import SysVar

logger = logging.getLogger(__name__)
router = APIRouter(tags=["avatar"])

_AVATAR_DIR: Path | None = None
_HTTP_CLIENT: httpx.AsyncClient | None = None


def _get_avatar_dir() -> Path:
    global _AVATAR_DIR
    if _AVATAR_DIR is None:
        _AVATAR_DIR = Path(SysVar.ACCOUNT_PATH) / "avatars"
        _AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    return _AVATAR_DIR


def _get_http_client() -> httpx.AsyncClient:
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        _HTTP_CLIENT = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
    return _HTTP_CLIENT


def _avatar_path(conv_id: str) -> Path:
    """Get the cache file path for a conversation's avatar."""
    h = hashlib.md5(conv_id.encode()).hexdigest()[:12]
    return _get_avatar_dir() / f"{h}.jpg"


def _has_valid_cache(conv_id: str, avatar_id: str | None) -> bool:
    """Check if a cached avatar file exists and is not stale."""
    if not avatar_id:
        return False
    path = _avatar_path(conv_id)
    return path.exists() and path.stat().st_size > 0


async def _fetch_and_cache_avatar(bot_id: str, jid: str, conv_id: str) -> tuple[str | None, bytes | None]:
    """Call contact.getavatar, download, cache, return (new_avatar_id, image_bytes).

    Returns (None, None) if the bot is offline or the command fails.
    """
    import asyncio

    try:
        result, error = await asyncio.to_thread(
            bot_manager.execute_cmd,
            bot_id=bot_id,
            cmd_name="contact.getavatar",
            args=[jid],
            options={},
            timeout=15.0,
        )
    except Exception as e:
        logger.debug(f"getavatar command failed for {conv_id}: {e}")
        return None, None

    if error or not result:
        logger.debug(f"getavatar error for {conv_id}: {error}")
        return None, None

    retcode = result.get("retcode", -1) if isinstance(result, dict) else -1
    if retcode != 0:
        logger.debug(f"getavatar non-zero retcode for {conv_id}: {retcode}")
        return None, None

    new_id = result.get("id")
    url = result.get("url")
    if not url:
        return None, None

    # Download the image
    try:
        client = _get_http_client()
        resp = await client.get(url)
        if resp.status_code != 200:
            logger.debug(f"avatar download failed for {conv_id}: HTTP {resp.status_code}")
            return None, None
        image_bytes = resp.content
    except Exception as e:
        logger.debug(f"avatar download error for {conv_id}: {e}")
        return None, None

    # Cache to disk
    path = _avatar_path(conv_id)
    try:
        path.write_bytes(image_bytes)
    except Exception as e:
        logger.warning(f"Failed to cache avatar for {conv_id}: {e}")

    return (str(new_id) if new_id else None), image_bytes


@router.get("/api/avatar/{conv_id:path}")
async def get_avatar(conv_id: str):
    """Serve the avatar image for a conversation.

    - Returns cached file if valid
    - Otherwise fetches via contact.getavatar and caches
    - Returns 404 if avatar unavailable (frontend falls back to colored circle)
    """
    conv = conv_store.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    bot_id = conv.get("bot_id", "")
    jid = conv.get("jid", "")
    avatar_id = conv.get("avatar_id")

    # 1. Return cached avatar if valid
    if _has_valid_cache(conv_id, avatar_id):
        path = _avatar_path(conv_id)
        return FileResponse(path, media_type="image/jpeg",
                           headers={"Cache-Control": "public, max-age=3600"})

    # 2. Try to fetch fresh avatar (requires bot online)
    if bot_id and jid:
        new_id, image_bytes = await _fetch_and_cache_avatar(bot_id, jid, conv_id)
        if image_bytes and len(image_bytes) > 0:
            # Update DB with new pictureId
            if new_id and new_id != avatar_id:
                conv_store.set_avatar_id(conv_id, new_id)
            return Response(content=image_bytes, media_type="image/jpeg",
                           headers={"Cache-Control": "public, max-age=3600"})

    # 3. No avatar available
    raise HTTPException(status_code=404, detail="Avatar not available")
