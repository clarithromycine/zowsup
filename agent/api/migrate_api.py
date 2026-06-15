"""
Agent-side remote migration endpoints.

POST /api/migrate/export  — tar + base64 the account directory
POST /api/migrate/import  — receive tar + base64, extract to ACCOUNT_PATH

Used by the Router to orchestrate automated bot migration between agents.
"""

from __future__ import annotations

import base64
import io
import logging
import shutil
import tarfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Body

from agent.manager.bot_manager import bot_manager
from conf.constants import SysVar

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/migrate", tags=["migrate"])


@router.post("/export")
async def export_bot(bot_id: str = Body(..., embed=True)):
    """Tar+base64 the bot's account directory. Bot must be stopped first."""
    account_dir = Path(SysVar.ACCOUNT_PATH) / bot_id
    if not account_dir.exists():
        raise HTTPException(status_code=404, detail=f"Account directory for '{bot_id}' not found")

    # Ensure bot is stopped
    if bot_manager.get_bot_instance(bot_id) is not None:
        raise HTTPException(status_code=409, detail=f"Bot '{bot_id}' is still running, stop first")

    # Detect env from config.json
    env = "android"
    config_path = account_dir / "config.json"
    if config_path.exists():
        import json
        try:
            cfg = json.loads(config_path.read_text())
            env = cfg.get("os_name", "android")
        except Exception:
            pass

    # Tar the directory
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(str(account_dir), arcname=bot_id)
    tar_b64 = base64.b64encode(buf.getvalue()).decode()

    logger.info("Exported bot '%s' (env=%s, size=%d bytes)", bot_id, env, len(tar_b64))
    return {"bot_id": bot_id, "env": env, "tar_b64": tar_b64}


@router.post("/import")
async def import_bot(
    bot_id: str = Body(..., embed=True),
    env: str = Body("android"),
    tar_b64: str = Body(..., embed=True),
):
    """Receive a tar+base64 account directory and extract it."""
    account_dir = Path(SysVar.ACCOUNT_PATH) / bot_id
    if account_dir.exists():
        raise HTTPException(status_code=409, detail=f"Account '{bot_id}' already exists at {account_dir}")

    try:
        data = base64.b64decode(tar_b64)
        buf = io.BytesIO(data)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            tar.extractall(path=Path(SysVar.ACCOUNT_PATH))
    except Exception as e:
        # Clean up partial extraction
        if account_dir.exists():
            shutil.rmtree(account_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Failed to extract: {e}")

    # Verify extraction
    if not account_dir.exists():
        raise HTTPException(status_code=500, detail="Extraction succeeded but directory not found")

    # Register in account store
    from agent.manager.account_store import account_store
    account_store.register(bot_id, env=env)

    logger.info("Imported bot '%s' (env=%s)", bot_id, env)
    return {"bot_id": bot_id, "env": env, "ok": True}


@router.post("/cleanup")
async def cleanup_bot(bot_id: str = Body(..., embed=True)):
    """Delete a bot's account directory and DB entry. Called after successful migration."""
    account_dir = Path(SysVar.ACCOUNT_PATH) / bot_id

    # Remove from account store
    from agent.manager.account_store import account_store
    account_store.remove(bot_id)

    # Remove account directory
    removed = False
    if account_dir.exists():
        shutil.rmtree(account_dir, ignore_errors=True)
        removed = True

    logger.info("Cleaned up bot '%s' (dir_removed=%s)", bot_id, removed)
    return {"bot_id": bot_id, "cleaned": True}
