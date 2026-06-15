"""Bot management API."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from agent.manager.bot_manager import bot_manager
from agent.manager.account_store import account_store
from agent.schemas import (
    BotInfo, BotStartRequest, BatchStartRequest, BatchStopRequest,
    BatchResult, BotImportRequest, BotExportRequest, BotExportEntry,
    BotStatus, PurgeRequest, PurgeResponse, PurgeResultEntry,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["bots"])
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@router.get("/api/listbot", response_model=list[BotInfo], response_model_exclude_none=True)
async def list_bots():
    return bot_manager.list_bots()


@router.get("/api/bot/{bot_id}", response_model=BotInfo, response_model_exclude_none=True)
async def get_bot(bot_id: str):
    info = bot_manager.get_bot(bot_id)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found")
    return info


@router.post("/api/startbot", response_model=BatchResult, response_model_exclude_none=True)
async def start_bots(req: BatchStartRequest):
    """Start bots concurrently. Mode: 'sync' (wait for logins) or 'fire' (return immediately)."""
    all_requests = list(req.bots) + [BotStartRequest(bot_id=bid) for bid in req.bot_ids]

    # ── Phase 1: Launch all bots concurrently ──
    async def _launch_one(bot_req: BotStartRequest) -> BotInfo:
        try:
            bot = await asyncio.to_thread(
                bot_manager.launch_bot,
                bot_id=bot_req.bot_id,
                env=bot_req.env.value if bot_req.env else None,
                proxy=bot_req.proxy,
                auto_login=bot_req.auto_login,
            )
            return BotInfo(bot_id=bot_req.bot_id, status=BotStatus.INITIAL, env=bot_req.env.value if bot_req.env else "")
        except ValueError as e:
            return BotInfo(bot_id=bot_req.bot_id, status=BotStatus.ERROR, error=str(e))
        except Exception as e:
            return BotInfo(bot_id=bot_req.bot_id, status=BotStatus.ERROR, error=str(e))

    launch_results = await asyncio.gather(*[_launch_one(r) for r in all_requests])
    launched_bots = [r for r in launch_results if r.status != BotStatus.ERROR]

    # ── Fire mode: return immediately ──
    if req.mode == "fire":
        success = len(launched_bots)
        errors = len(launch_results) - success
        return BatchResult(results=launch_results, success_count=success, error_count=errors)

    # ── Sync mode: wait for all logins concurrently ──
    async def _wait_one(bot_id: str) -> BotInfo:
        try:
            bot = await asyncio.to_thread(bot_manager.get_bot_instance, bot_id)
            if bot is None:
                return BotInfo(bot_id=bot_id, status=BotStatus.ERROR, error="Bot instance lost")
            return await asyncio.to_thread(bot_manager.wait_bot_login, bot)
        except Exception as e:
            return BotInfo(bot_id=bot_id, status=BotStatus.ERROR, error=str(e))

    login_results = await asyncio.gather(*[_wait_one(r.bot_id) for r in launched_bots])

    # Merge: errors from phase 1 + results from phase 2
    final_results = [r for r in launch_results if r.status == BotStatus.ERROR] + list(login_results)
    success = sum(1 for r in login_results if r.status == BotStatus.RUNNING)
    errors = len(final_results) - success
    return BatchResult(results=final_results, success_count=success, error_count=errors)


@router.post("/api/stopbot", response_model=BatchResult, response_model_exclude_none=True)
async def stop_bots(req: BatchStopRequest):
    results = []; success = 0; errors = 0
    for bot_id in req.bot_ids:
        info = bot_manager.stop_bot(bot_id)
        if info is None:
            results.append(BotInfo(bot_id=bot_id, status="ERROR", error="Bot not running")); errors += 1
        else:
            results.append(info); success += 1
    return BatchResult(results=results, success_count=success, error_count=errors)


@router.post("/api/importbot", response_model=BatchResult, response_model_exclude_none=True)
async def import_accounts(req: BotImportRequest):
    results = []; success = 0; errors = 0
    for item in req.accounts:
        if not item.data or item.data.count(",") != 5:
            phone = item.data.split(",")[0].strip() if item.data else "unknown"
            results.append(BotInfo(bot_id=phone, status="ERROR", error="Invalid CSV (need 6 fields)")); errors += 1; continue
        phone = item.data.split(",")[0].strip()
        if not phone:
            results.append(BotInfo(bot_id="unknown", status="ERROR", error="No phone")); errors += 1; continue
        env = item.env.value
        cmd = [sys.executable, str(_PROJECT_ROOT / "script" / "import6.py"), item.data, "--env", env]
        try:
            r = subprocess.run(cmd, cwd=str(_PROJECT_ROOT), capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                results.append(BotInfo(bot_id=phone, status="ERROR", error=f"Import failed: {r.stderr[:200]}")); errors += 1
            else:
                account_store.register(phone, env=env)
                account_store.update_status(phone, "stopped", env=env)
                results.append(BotInfo(bot_id=phone, status="STOPPED")); success += 1
        except subprocess.TimeoutExpired:
            results.append(BotInfo(bot_id=phone, status="ERROR", error="Timeout")); errors += 1
        except Exception as e:
            results.append(BotInfo(bot_id=phone, status="ERROR", error=str(e))); errors += 1
    return BatchResult(results=results, success_count=success, error_count=errors)


@router.post("/api/exportbot", response_model=dict)
async def export_accounts(req: BotExportRequest):
    """Export accounts. Returns {bot_id: {data: csv, env: str}}."""
    result = {}
    for bot_id in req.bot_ids:
        # Resolve env from account store or bot manager
        env = ""
        acct = account_store.get(bot_id)
        if acct:
            env = acct.get("env", "")
        if not env:
            info = bot_manager.get_bot(bot_id)
            if info:
                env = info.env or ""

        cmd = [sys.executable, str(_PROJECT_ROOT / "script" / "export6.py"), bot_id]
        try:
            r = subprocess.run(cmd, cwd=str(_PROJECT_ROOT), capture_output=True, text=True, timeout=30)
            data = r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None
        except Exception:
            data = None
        result[bot_id] = {"data": data, "env": env}
    return {"exports": result}


@router.post("/api/purgebot", response_model=PurgeResponse, response_model_exclude_none=True)
async def purge_accounts(req: PurgeRequest):
    """Permanently delete bot accounts: stop bot, remove DB record, delete local data directory.

    mode="auto": purge ALL accounts that are auth_failed OR orphaned (DB entry with no data dir).
    mode="list": purge only specified bot_ids that are in auth_failed state.

    Use with caution — this operation cannot be undone.
    """
    raw_results = await asyncio.to_thread(
        bot_manager.purge_accounts,
        mode=req.mode,
        bot_ids=req.bot_ids,
    )
    results = {
        bot_id: PurgeResultEntry(**entry)
        for bot_id, entry in raw_results.items()
    }
    return PurgeResponse(results=results)
