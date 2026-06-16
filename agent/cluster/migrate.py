"""
Bot migration orchestration between agents.

Phase E: robust rollback, state tracking, status API.
"""

from __future__ import annotations

import logging
import time

from fastapi import Request, HTTPException

from agent.cluster.registry import registry
from agent.cluster.helpers import proxy_json

logger = logging.getLogger(__name__)

# ── Migration state tracker ──────────────────────────────────────────────────

_migration_states: dict[str, dict] = {}  # bot_id → {stage, from, to, started_at, error, ...}

_STAGE_ORDER = [
    "init",           # → stopping on source
    "stopped",        # → exporting from source
    "exported",       # → importing to target
    "imported",       # → starting on target
    "starting",       # → updating routing
    "migrated",       # → cleaning up source
    "done",           # final
]

def _set_state(bot_id: str, stage: str, **kwargs):
    entry = _migration_states.setdefault(bot_id, {"bot_id": bot_id, "started_at": time.time()})
    entry["stage"] = stage
    entry["updated_at"] = time.time()
    entry.update(kwargs)
    logger.info("Migration '%s' → %s", bot_id, stage)

def get_migration_status(bot_id: str | None = None) -> dict | list[dict]:
    """Return status for one or all migrations."""
    if bot_id:
        return _migration_states.get(bot_id, {"bot_id": bot_id, "stage": "unknown"})
    return list(_migration_states.values())


async def migrate_bot(request: Request) -> dict:
    """Automated bot migration with full rollback on failure.

    Flow: stop → export → import → start → route → cleanup.
    Each failed step triggers a rollback to restore the original state.
    """
    body = await request.json()
    bot_id = body.get("bot_id")
    target_agent_id = body.get("target_agent")
    if not bot_id or not target_agent_id:
        raise HTTPException(status_code=400, detail="bot_id and target_agent required")

    route = registry.resolve_bot(bot_id)
    if not route:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found in routing table")

    source_id = route["agent_id"]
    source_url = route["url"]

    if source_id == target_agent_id:
        raise HTTPException(status_code=400, detail="Source and target agent are the same")

    target = registry.get_agent(target_agent_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"Target agent '{target_agent_id}' not found")
    target_url = target["url"]

    # ── Capacity check ──────────────────────────────────────────────────
    target_bot_count = len(registry.list_bot_routes(target_agent_id))
    if target_bot_count >= registry.MAX_BOTS_PER_AGENT:
        raise HTTPException(
            status_code=429,
            detail=f"Target agent '{target_agent_id}' at capacity "
                   f"({target_bot_count}/{registry.MAX_BOTS_PER_AGENT} bots)",
        )

    _set_state(bot_id, "init", from_agent=source_id, to_agent=target_agent_id)

    # ── 1. Stop bot on source ───────────────────────────────────────────
    _set_state(bot_id, "stopping")
    stop = await proxy_json(source_url, "POST", "/api/stopbot",
                            {"bot_ids": [bot_id], "mode": "force"})
    if not stop or stop.get("error_count", 0) > 0:
        _set_state(bot_id, "failed", error="stop_failed", detail=str(stop))
        raise HTTPException(status_code=500, detail="Failed to stop bot on source agent")
    _set_state(bot_id, "stopped")

    # ── 2. Export from source ───────────────────────────────────────────
    _set_state(bot_id, "exporting")
    export = await proxy_json(source_url, "POST", "/api/migrate/export", {"bot_id": bot_id})
    if not export or not export.get("tar_b64"):
        # Rollback: restart bot on source
        _ = await proxy_json(source_url, "POST", "/api/startbot", {"bot_ids": [bot_id]})
        _set_state(bot_id, "rolled_back", error="export_failed")
        raise HTTPException(status_code=500, detail="Export failed — rolled back, bot restarted on source")
    env = export.get("env", "android")
    tar_b64 = export["tar_b64"]
    _set_state(bot_id, "exported")

    # ── 3. Import to target ─────────────────────────────────────────────
    _set_state(bot_id, "importing")
    imp = await proxy_json(target_url, "POST", "/api/migrate/import",
                           {"bot_id": bot_id, "env": env, "tar_b64": tar_b64})
    if not imp or not imp.get("ok"):
        # Rollback: restart bot on source (account dir is still there)
        _ = await proxy_json(source_url, "POST", "/api/startbot", {"bot_ids": [bot_id]})
        _set_state(bot_id, "rolled_back", error="import_failed")
        raise HTTPException(status_code=500, detail="Import failed — rolled back, bot restarted on source")
    _set_state(bot_id, "imported")

    # ── 4. Start bot on target ──────────────────────────────────────────
    _set_state(bot_id, "starting")
    start = await proxy_json(target_url, "POST", "/api/startbot", {"bot_ids": [bot_id]})
    if not start or start.get("error_count", 0) > 0:
        # Rollback: remove from target, restart on source
        _ = await proxy_json(target_url, "POST", "/api/bot/" + bot_id, method_override="DELETE")
        _ = await proxy_json(source_url, "POST", "/api/startbot", {"bot_ids": [bot_id]})
        _set_state(bot_id, "rolled_back", error="start_failed_on_target")
        raise HTTPException(status_code=500, detail="Start on target failed — rolled back, restarted on source")

    # ── 5. Update routing table ─────────────────────────────────────────
    _set_state(bot_id, "routing")
    registry.route_bot(bot_id, target_agent_id)

    # ── 6. Clean up source agent ────────────────────────────────────────
    _set_state(bot_id, "cleaning")
    _ = await proxy_json(source_url, "POST", "/api/migrate/cleanup", {"bot_id": bot_id})

    _set_state(bot_id, "done")
    return {"bot_id": bot_id, "from": source_id, "to": target_agent_id, "status": "migrated"}
