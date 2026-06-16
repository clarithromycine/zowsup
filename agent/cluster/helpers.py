"""
Shared helpers for cluster Router endpoints.

Extracted from router.py to keep the route-definition file lean.
"""

from __future__ import annotations

import logging

from fastapi import Request, HTTPException

from agent.cluster.proxy import proxy_http, _extract_bot_id_from_body
from agent.cluster.registry import registry

logger = logging.getLogger(__name__)


async def proxy_with_body_fallback(request: Request):
    """Try extracting bot_id from body, else pick any online agent."""
    bot_id = await _extract_bot_id_from_body(request)
    if bot_id:
        route = registry.resolve_bot(bot_id)
        if route:
            return await proxy_http(request, route["url"])

    # Fallback: pick any online agent
    agent = registry.pick_agent()
    if not agent:
        raise HTTPException(status_code=503, detail="No online agent available")
    return await proxy_http(request, agent["url"])


async def proxy_json(agent_url: str, method: str, path: str, body: dict) -> dict | None:
    """Make a JSON request to an agent and return parsed response."""
    from agent.cluster.proxy import _get_client
    client = _get_client()
    try:
        resp = await client.request(
            method=method, url=f"{agent_url}{path}",
            json=body, timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as exc:
        logger.warning("proxy_json %s %s failed: %s", method, path, exc)
    return None
