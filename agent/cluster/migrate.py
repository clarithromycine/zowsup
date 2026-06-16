"""
Bot migration orchestration between agents.

Extracted from router.py — handles the multi-step stop → export →
import → start → route-update flow with partial rollback.
"""

from __future__ import annotations

import logging

from fastapi import Request, HTTPException

from agent.cluster.registry import registry
from agent.cluster.helpers import proxy_json

logger = logging.getLogger(__name__)


async def migrate_bot(request: Request) -> dict:
    """Automated bot migration between agents.

    Flow: stop → export from source → import to target → start → update route.
    Uses agent-side /api/migrate/export and /api/migrate/import endpoints.

    Returns {"bot_id", "from", "to", "status": "migrated"} on success.
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

    # ── Capacity check: reject if target would exceed max bots ───────────
    target_bot_count = len(registry.list_bot_routes(target_agent_id))
    if target_bot_count >= registry.MAX_BOTS_PER_AGENT:
        raise HTTPException(
            status_code=429,
            detail=f"Target agent '{target_agent_id}' at capacity "
                   f"({target_bot_count}/{registry.MAX_BOTS_PER_AGENT} bots)",
        )

    # 1. Stop bot on source agent
    logger.info("Migrating bot '%s': %s → %s", bot_id, source_id, target_agent_id)
    _ = await proxy_json(source_url, "POST", "/api/stopbot",
                         {"bot_ids": [bot_id], "mode": "force"})

    # 2. Export from source agent
    export = await proxy_json(source_url, "POST", "/api/migrate/export", {"bot_id": bot_id})
    if not export or not export.get("tar_b64"):
        raise HTTPException(status_code=500, detail="Export failed — agent returned no data")
    env = export.get("env", "android")
    tar_b64 = export["tar_b64"]

    # 3. Import to target agent
    imp = await proxy_json(target_url, "POST", "/api/migrate/import",
                           {"bot_id": bot_id, "env": env, "tar_b64": tar_b64})
    if not imp or not imp.get("ok"):
        # Try to restart on source as rollback
        logger.warning("Import to %s failed, rolling back on %s", target_agent_id, source_id)
        _ = await proxy_json(source_url, "POST", "/api/startbot", {"bot_ids": [bot_id]})
        raise HTTPException(status_code=500, detail="Import failed — rolled back")

    # 4. Start bot on target agent
    _ = await proxy_json(target_url, "POST", "/api/startbot", {"bot_ids": [bot_id]})

    # 5. Update routing table
    registry.route_bot(bot_id, target_agent_id)

    # 6. Clean up source agent (delete account dir + DB entry)
    _ = await proxy_json(source_url, "POST", "/api/migrate/cleanup", {"bot_id": bot_id})
    logger.info("Bot '%s' migrated: %s → %s", bot_id, source_id, target_agent_id)

    return {"bot_id": bot_id, "from": source_id, "to": target_agent_id, "status": "migrated"}
