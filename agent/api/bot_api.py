"""
Bot management API endpoints.

GET    /api/bots              — list all bots
GET    /api/bots/{bot_id}     — get bot info
POST   /api/startbots         — start one or more bots
POST   /api/stopbots          — stop one or more bots
POST   /api/bots/import       — import account (import6 format)
GET    /api/bots/{bot_id}/export — export account (export6 format)
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from agent.manager.bot_manager import bot_manager
from agent.manager.account_store import account_store
from agent.schemas import (
    BotInfo, BotStartRequest,
    BatchStartRequest, BatchStopRequest, BatchResult,
    BotImportRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["bots"])

# Project root for subprocess calls
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ── List bots ────────────────────────────────────────────────────────────────

@router.get("/api/bots", response_model=list[BotInfo])
async def list_bots():
    """Return all managed accounts and their statuses."""
    return bot_manager.list_bots()


# ── Get single bot ───────────────────────────────────────────────────────────

@router.get("/api/bots/{bot_id}", response_model=BotInfo)
async def get_bot(bot_id: str):
    """Return info for a specific bot."""
    info = bot_manager.get_bot(bot_id)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found")
    return info


# ── Batch Start ──────────────────────────────────────────────────────────────

@router.post("/api/startbots", response_model=BatchResult)
async def start_bots(req: BatchStartRequest):
    """Start one or more bots. Each bot is started in its own thread.

    Returns results for all bots — some may have started successfully
    while others may have failed.
    """
    results = []
    success = 0
    errors = 0

    # Merge both sources: full objects + plain IDs
    all_requests = list(req.bots) + [BotStartRequest(bot_id=bid) for bid in req.bot_ids]

    for bot_req in all_requests:
        try:
            info = bot_manager.start_bot(
                bot_id=bot_req.bot_id,
                env=bot_req.env.value if bot_req.env else None,
                proxy=bot_req.proxy,
                auto_login=bot_req.auto_login,
            )
            results.append(info)
            success += 1
        except ValueError as e:
            results.append(BotInfo(
                bot_id=bot_req.bot_id, status="ERROR", error=str(e),
            ))
            errors += 1
        except Exception as e:
            logger.error(f"Failed to start bot '{bot_req.bot_id}': {e}", exc_info=True)
            results.append(BotInfo(
                bot_id=bot_req.bot_id, status="ERROR", error=str(e),
            ))
            errors += 1

    return BatchResult(results=results, success_count=success, error_count=errors)


# ── Batch Stop ───────────────────────────────────────────────────────────────

@router.post("/api/stopbots", response_model=BatchResult)
async def stop_bots(req: BatchStopRequest):
    """Stop one or more bots. Each bot is stopped and its thread joined.

    Returns results for all requested bots.
    """
    results = []
    success = 0
    errors = 0

    for bot_id in req.bot_ids:
        info = bot_manager.stop_bot(bot_id)
        if info is None:
            info = BotInfo(bot_id=bot_id, status="ERROR", error="Bot not running")
            errors += 1
        else:
            success += 1
        results.append(info)

    return BatchResult(results=results, success_count=success, error_count=errors)


# ── Import account ───────────────────────────────────────────────────────────


@router.post("/api/bots/import", response_model=dict)
async def import_account(req: BotImportRequest):
    """Import a bot account using the import6 6-segment CSV format.

    The data field should contain a comma-separated string with 6 fields:
    phone,pk1,sk1,pk2,sk2,sixth

    The phone field is extracted as the bot_id.
    """
    if not req.data or req.data.count(",") != 5:
        raise HTTPException(
            status_code=400,
            detail="Invalid import data: expected exactly 6 comma-separated fields (phone,pk1,sk1,pk2,sk2,sixth)",
        )

    # Extract bot_id from the first field (phone number)
    phone = req.data.split(",")[0].strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Could not extract phone number from import data")

    # Determine env from request
    env = req.env.value if req.env else "android"

    cmd = [sys.executable, str(_PROJECT_ROOT / "script" / "import6.py"), req.data, "--env", env]
    logger.info(f"Importing account {phone} via: {' '.join(cmd[:2])} ...")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.error(f"Import failed: {result.stderr}")
            raise HTTPException(
                status_code=500,
                detail=f"Import failed (exit {result.returncode}): {result.stderr[:500]}",
            )
        # Register in account store
        account_store.register(phone, env=env)
        return {"bot_id": phone, "imported": True, "stdout": result.stdout}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Import timed out after 30s")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Import error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Export account ───────────────────────────────────────────────────────────


@router.get("/api/bots/{bot_id}/export", response_model=dict)
async def export_account(bot_id: str):
    """Export a bot account using the export6 6-segment CSV format.

    Returns a JSON object with the bot_id and the CSV data string.
    """
    cmd = [sys.executable, str(_PROJECT_ROOT / "script" / "export6.py"), bot_id]
    logger.info(f"Exporting account {bot_id}")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Export failed (exit {result.returncode}): {result.stderr[:500]}",
            )
        data = result.stdout.strip()
        if not data:
            raise HTTPException(status_code=404, detail=f"No export data for bot '{bot_id}'")
        return {"bot_id": bot_id, "data": data}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Export timed out after 30s")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
