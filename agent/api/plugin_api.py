"""Plugin configuration API.

GET    /api/plugin                          — list plugins & state
GET    /api/plugin/{name}/config?bot_id=    — get plugin config
PUT    /api/plugin/{name}/config?bot_id=    — update plugin config
PUT    /api/plugin/{name}/enabled           — enable/disable plugin
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Body

from agent.plugin.manager import plugin_manager
from agent.plugin.store import plugin_store

router = APIRouter(prefix="/api/plugin", tags=["plugins"])


# ── List ─────────────────────────────────────────────────────────────────────

@router.get("")
async def list_plugins():
    """List all registered plugins with their global enable state."""
    result = []
    for name in plugin_manager.names:
        p = plugin_manager.get(name)
        if p is None:
            continue
        enabled = plugin_store.is_enabled(name)
        result.append({
            "name": name,
            "version": p.version,
            "description": p.description,
            "priority": p.priority,
            "enabled": enabled,
        })
    return result


# ── Get Config ───────────────────────────────────────────────────────────────

@router.get("/{plugin_name}/config")
async def get_plugin_config(
    plugin_name: str,
    bot_id: str | None = None,
):
    if plugin_manager.get(plugin_name) is None:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found")

    cfg = plugin_store.get_config(plugin_name, bot_id)
    enabled = plugin_store.is_enabled(plugin_name, bot_id)
    # If stored as raw inner config, wrap; otherwise return wrapper as-is
    if isinstance(cfg, dict) and "plugin" not in cfg:
        return {
            "plugin": plugin_name,
            "bot_id": bot_id or "(global)",
            "enabled": enabled,
            "config": cfg,
        }
    # Wrapper format: sync enabled from DB (toggle updates column, not config_json)
    cfg["enabled"] = enabled
    return cfg


# ── Update Config ────────────────────────────────────────────────────────────

@router.put("/{plugin_name}/config")
async def update_plugin_config(
    plugin_name: str,
    config: dict = Body(...),
    bot_id: str = "",
):
    if plugin_manager.get(plugin_name) is None:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found")

    plugin_store.set_config(plugin_name, config, bot_id)
    # Sync enabled toggle: if the config JSON has an "enabled" key, update the DB column too
    if "enabled" in config:
        plugin_store.set_enabled(plugin_name, bool(config["enabled"]), bot_id)
    updated = plugin_store.get_config(plugin_name, bot_id if bot_id else None)
    if isinstance(updated, dict):
        updated["enabled"] = plugin_store.is_enabled(plugin_name, bot_id if bot_id else None)
    return updated


# ── Enable / Disable ─────────────────────────────────────────────────────────

@router.put("/{plugin_name}/enabled")
async def set_plugin_enabled(
    plugin_name: str,
    enabled: bool = Body(..., embed=True),
    bot_id: str = "",
):
    if plugin_manager.get(plugin_name) is None:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found")

    plugin_store.set_enabled(plugin_name, enabled, bot_id)
    return {
        "plugin": plugin_name,
        "bot_id": bot_id or "(global)",
        "enabled": enabled,
    }


# ── Cluster reload (called by Router on config change) ──────────────────────

@router.post("/reload")
async def reload_plugins():
    """Re-sync plugin config from Router. Called via notification."""
    import os
    cluster_url = os.environ.get("CLUSTER_URL", "")
    if not cluster_url:
        return {"ok": True, "synced": 0, "reason": "no CLUSTER_URL"}

    import httpx
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10)) as client:
            resp = await client.get(f"{cluster_url}/api/plugin/sync")
            if resp.status_code == 200:
                rows = resp.json()
                if isinstance(rows, list):
                    plugin_store.import_from(rows)
                    return {"ok": True, "synced": len(rows)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "synced": 0}
