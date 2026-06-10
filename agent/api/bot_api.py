"""Bot management API."""

from __future__ import annotations

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
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["bots"])
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@router.get("/api/listbot", response_model=list[BotInfo])
async def list_bots():
    return bot_manager.list_bots()


@router.get("/api/bot/{bot_id}", response_model=BotInfo)
async def get_bot(bot_id: str):
    info = bot_manager.get_bot(bot_id)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found")
    return info


@router.post("/api/startbot", response_model=BatchResult)
async def start_bots(req: BatchStartRequest):
    results = []; success = 0; errors = 0
    all_requests = list(req.bots) + [BotStartRequest(bot_id=bid) for bid in req.bot_ids]
    for bot_req in all_requests:
        try:
            info = bot_manager.start_bot(bot_id=bot_req.bot_id, env=bot_req.env.value if bot_req.env else None, proxy=bot_req.proxy, auto_login=bot_req.auto_login)
            results.append(info); success += 1
        except ValueError as e:
            results.append(BotInfo(bot_id=bot_req.bot_id, status="ERROR", error=str(e))); errors += 1
        except Exception as e:
            results.append(BotInfo(bot_id=bot_req.bot_id, status="ERROR", error=str(e))); errors += 1
    return BatchResult(results=results, success_count=success, error_count=errors)


@router.post("/api/stopbot", response_model=BatchResult)
async def stop_bots(req: BatchStopRequest):
    results = []; success = 0; errors = 0
    for bot_id in req.bot_ids:
        info = bot_manager.stop_bot(bot_id)
        if info is None:
            results.append(BotInfo(bot_id=bot_id, status="ERROR", error="Bot not running")); errors += 1
        else:
            results.append(info); success += 1
    return BatchResult(results=results, success_count=success, error_count=errors)


@router.post("/api/importbot", response_model=BatchResult)
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
