"""
Router — transparent HTTP proxy for multi-agent clusters.

Exposes the SAME API as a single agent.  Internally routes
bot-specific requests to the correct agent via the registry.

Usage:
    python -m agent.cluster.router --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketException, Header, Depends
from starlette.responses import Response

from agent.cluster.proxy import proxy_http, scatter_gather, proxy_ws
from agent.cluster.registry import registry

logger = logging.getLogger(__name__)

# ── Cluster Secret ───────────────────────────────────────────────────────────

_cluster_secret: str | None = None
_console_token: str | None = None


def set_cluster_secret(secret: str | None) -> None:
    """Configure the shared cluster secret for agent authentication."""
    global _cluster_secret
    _cluster_secret = secret


def set_console_token(token: str | None) -> None:
    """Configure an optional console bearer token."""
    global _console_token
    _console_token = token


async def _check_cluster_secret(x_cluster_secret: str | None = Header(None, alias="X-Cluster-Secret")) -> None:
    """FastAPI dependency: verify X-Cluster-Secret header.

    Raises HTTPException(403) if cluster secret is configured and header is
    missing or wrong.  No-op when cluster_secret is None (backward compatible).
    """
    if _cluster_secret is None:
        return  # Auth disabled — backward compatible
    if x_cluster_secret != _cluster_secret:
        raise HTTPException(status_code=403, detail="Invalid or missing cluster secret")


# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    registry.start()
    health_task = asyncio.ensure_future(_health_check_loop())
    logger.info("Cluster started")
    yield
    health_task.cancel()
    from agent.cluster.proxy import close_client
    await close_client()
    logger.info("Cluster stopped")


# ── Health checker ───────────────────────────────────────────────────────────

async def _health_check_loop(interval: float = 15.0):
    """Periodically ping all agents. 3 consecutive failures → mark offline."""
    fail_counts: dict[str, int] = {}
    while True:
        await asyncio.sleep(interval)
        for agent in registry.list_agents():
            if agent["status"] == "offline":
                continue
            ok = await _ping_agent(agent["url"])
            aid = agent["agent_id"]
            if ok:
                fail_counts.pop(aid, None)
                registry.heartbeat(aid)
            else:
                fail_counts[aid] = fail_counts.get(aid, 0) + 1
                if fail_counts[aid] >= 3:
                    logger.warning("Agent '%s' marked offline after 3 failed pings", aid)
                    registry.mark_offline(aid)


async def _ping_agent(url: str) -> bool:
    try:
        from agent.cluster.proxy import _get_client
        client = _get_client()
        resp = await client.get(f"{url}/api/health", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


# ── App ──────────────────────────────────────────────────────────────────────

def create_cluster_app() -> FastAPI:
    app = FastAPI(title="Zowsup Cluster", version="0.1.0", lifespan=lifespan)

    # ── Cluster management (auth required when CLUSTER_SECRET is set) ─────
    from fastapi.routing import APIRouter
    cluster_router = APIRouter(dependencies=[Depends(_check_cluster_secret)])

    @cluster_router.get("/api/cluster/agents")
    async def list_agents():
        agents = registry.list_agents()
        for a in agents:
            bots = registry.list_bot_routes(a["agent_id"])
            a["bot_count"] = len(bots)
            a["bots"] = [b["bot_id"] for b in bots]
        return agents

    @cluster_router.post("/api/cluster/agents")
    async def register_agent(request: Request):
        body = await request.json()
        agent_id = body.get("agent_id")
        url = body.get("url")
        if not agent_id or not url:
            raise HTTPException(status_code=400, detail="agent_id and url required")
        agent = registry.register_agent(agent_id, url, body.get("access_key", ""))
        # Sync bot routes from agent
        bots = body.get("bots", [])
        for bot_id in bots:
            registry.route_bot(bot_id, agent_id)
        return agent

    @cluster_router.delete("/api/cluster/agents/{agent_id}")
    async def unregister_agent(agent_id: str):
        if not registry.unregister_agent(agent_id):
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        return {"unregistered": agent_id}

    @cluster_router.post("/api/cluster/agents/{agent_id}/heartbeat")
    async def agent_heartbeat(agent_id: str, request: Request):
        body = await request.json() if request.headers.get("content-type") else {}
        bots = body.get("bots", [])
        # Sync bot routes
        for bot_id in bots:
            registry.route_bot(bot_id, agent_id)
        if not registry.heartbeat(agent_id):
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        return {"ok": True}

    @cluster_router.post("/api/cluster/migrate")
    async def _migrate_bot(request: Request):
        """Automated bot migration between agents.
        Flow: stop → export from source → import to target → start → update route.
        """
        from agent.cluster.migrate import migrate_bot
        return await migrate_bot(request)

    # Register cluster management routes (all guarded by _check_cluster_secret)
    app.include_router(cluster_router)

    # ── Aggregate endpoints ──────────────────────────────────────────────────

    @app.get("/api/listbot")
    async def list_bots():
        """Aggregate bots from all agents, tagging each with its agent_id."""
        results = []
        for agent in registry.list_agents():
            if agent["status"] != "online":
                continue
            try:
                from agent.cluster.proxy import _get_client
                client = _get_client()
                resp = await client.get(f"{agent['url']}/api/listbot", timeout=10)
                if resp.status_code == 200:
                    bots = resp.json()
                    if isinstance(bots, list):
                        for b in bots:
                            b["agent_id"] = agent["agent_id"]
                        results.extend(bots)
            except Exception as exc:
                logger.debug("listbot failed for %s: %s", agent["agent_id"], exc)
        return results

    @app.get("/api/health")
    async def health():
        agents = registry.list_agents()
        online = sum(1 for a in agents if a["status"] == "online")
        return {
            "status": "ok",
            "version": "cluster-0.1.0",
            "uptime_seconds": int(time.time() - _start_time),
            "agents_total": len(agents),
            "agents_online": online,
        }

    # ── Bot-specific proxy ───────────────────────────────────────────────────

    @app.api_route("/api/bot/{bot_id}/{rest:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def proxy_bot_api(bot_id: str, rest: str, request: Request):
        route = registry.resolve_bot(bot_id)
        if not route:
            raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not routed to any agent")
        return await proxy_http(request, route["url"])

    @app.api_route("/api/bot/{bot_id}", methods=["GET", "POST", "PUT", "DELETE"])
    async def proxy_bot_root(bot_id: str, request: Request):
        route = registry.resolve_bot(bot_id)
        if not route:
            raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not routed to any agent")
        return await proxy_http(request, route["url"])

    # ── Conversation proxy ───────────────────────────────────────────────────
    # conv_id format: bot_id:jid → extract bot_id

    @app.api_route("/api/conversation/{conv_id:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def proxy_conversation(conv_id: str, request: Request):
        bot_id = conv_id.split(":")[0] if ":" in conv_id else None
        if not bot_id:
            return await proxy_with_body_fallback(request)
        route = registry.resolve_bot(bot_id)
        if not route:
            raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not routed")
        return await proxy_http(request, route["url"])

    @app.get("/api/conversation")
    async def proxy_conversation_list(request: Request):
        # Route by bot_id query param
        bot_id = request.query_params.get("bot_id")
        if bot_id:
            route = registry.resolve_bot(bot_id)
            if route:
                return await proxy_http(request, route["url"])
        return await proxy_with_body_fallback(request)

    # ── Send message proxy ───────────────────────────────────────────────────

    @app.post("/api/sendmsg")
    async def proxy_sendmsg(request: Request):
        return await proxy_with_body_fallback(request)

    # ── Escalation (centralized) ──────────────────────────────────────────────

    from agent.manager.escalation_queue import get_cluster_queue
    _esc_queue = None

    def _get_esc():
        nonlocal _esc_queue
        if _esc_queue is None:
            _esc_queue = get_cluster_queue()
        return _esc_queue

    @app.get("/api/escalation")
    async def list_escalations(
        status: str | None = None,
        bot_id: str | None = None,
    ):
        """List escalations from centralized Router store."""
        items = _get_esc().list(status=status, bot_id=bot_id)
        result = []
        for item in items:
            conv_id = item["conversation_id"]
            bot_id2 = conv_id.split(":")[0] if ":" in conv_id else ""
            conv = None
            if bot_id2:
                route = registry.resolve_bot(bot_id2)
                if route:
                    try:
                        from agent.cluster.proxy import _get_client
                        client = _get_client()
                        resp = await client.get(f"{route['url']}/api/conversation/{conv_id}?limit=1", timeout=5)
                        if resp.status_code == 200:
                            conv = resp.json()
                    except Exception:
                        pass
            if conv and "messages" in conv:
                del conv["messages"]
            result.append({**item, "conversation": conv})
        return result

    @app.get("/api/escalation/{esc_id}")
    async def get_escalation(esc_id: str):
        esc = _get_esc().get(esc_id)
        if esc is None:
            raise HTTPException(status_code=404, detail=f"Escalation {esc_id} not found")
        return esc

    @app.post("/api/escalation")
    async def create_escalation(request: Request):
        """Receive escalation from an agent (cluster mode)."""
        body = await request.json()
        esc = _get_esc().add(
            bot_id=body.get("bot_id", ""),
            conversation_id=body.get("conversation_id", ""),
            reason=body.get("reason", ""),
            priority=body.get("priority", "normal"),
            agent_id=body.get("agent_id", ""),
            escalation_id=body.get("id", ""),
        )
        return esc

    @app.api_route("/api/escalation/{esc_id}/{action}", methods=["POST"])
    async def escalation_action(esc_id: str, action: str, request: Request):
        """Handle claim/unclaim/resolve/reply for a single escalation."""
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass

        if action == "claim":
            operator = body.get("operator", body.get("claimed_by", "unknown"))
            if not _get_esc().claim(esc_id, operator):
                raise HTTPException(status_code=409, detail="Already claimed or not found")
            return {"id": esc_id, "claimed_by": operator, "status": "claimed"}

        elif action == "unclaim":
            if not _get_esc().unclaim(esc_id):
                raise HTTPException(status_code=409, detail="Not claimed or not found")
            return {"id": esc_id, "status": "pending"}

        elif action == "resolve":
            if not _get_esc().resolve(esc_id):
                raise HTTPException(status_code=404, detail="Not found")
            return {"id": esc_id, "status": "resolved"}

        elif action == "reply":
            text = body.get("text", "")
            if not text:
                raise HTTPException(status_code=400, detail="text required")
            esc = _get_esc().get(esc_id)
            if esc is None:
                raise HTTPException(status_code=404, detail="Not found")
            conv_id = esc["conversation_id"]
            parts = conv_id.split(":", 1)
            if len(parts) != 2:
                raise HTTPException(status_code=400, detail="Invalid conversation_id")
            bot_id2, jid = parts
            route = registry.resolve_bot(bot_id2)
            if not route:
                raise HTTPException(status_code=404, detail=f"Bot '{bot_id2}' not routed")
            from agent.cluster.proxy import _get_client
            client = _get_client()
            resp = await client.post(
                f"{route['url']}/api/conversation/{conv_id}/message",
                json={"content": text},
                timeout=30,
            )
            if resp.status_code != 200:
                detail = ""
                try: detail = resp.json().get("detail", "")
                except: pass
                raise HTTPException(status_code=resp.status_code, detail=f"Send failed: {detail}")
            return {"sent": True, "conversation_id": conv_id, "text": text}

        else:
            raise HTTPException(status_code=404, detail=f"Unknown action: {action}")

    # ── Plugin API (centralized) ──────────────────────────────────────────────

    from agent.plugin.store import get_cluster_plugin_store
    _plugin_store = None

    def _get_ps():
        nonlocal _plugin_store
        if _plugin_store is None:
            _plugin_store = get_cluster_plugin_store()
        return _plugin_store

    @app.get("/api/plugin")
    async def list_plugins():
        """List plugins from central store."""
        ps = _get_ps()
        result = []
        for name in ("translation", "ai"):
            enabled = ps.is_enabled(name)
            result.append({"name": name, "version": "0.1.0", "description": "", "priority": 10 if name == "translation" else 100, "enabled": enabled})
        return result

    @app.get("/api/plugin/sync")
    async def sync_plugins():
        """Return all plugin configs for agent sync."""
        ps = _get_ps()
        return ps.export_all()

    @app.get("/api/plugin/{plugin_name}/config")
    async def get_plugin_config(plugin_name: str, bot_id: str = ""):
        ps = _get_ps()
        config = ps.get_config(plugin_name, bot_id if bot_id else None)
        enabled = ps.is_enabled(plugin_name, bot_id if bot_id else None)
        return {"plugin": plugin_name, "bot_id": bot_id or "(global)", "enabled": enabled, "config": config}

    @app.put("/api/plugin/{plugin_name}/config")
    async def update_plugin_config(plugin_name: str, request: Request):
        body = await request.json()
        config = body if isinstance(body, dict) else {}
        bot_id = body.pop("bot_id", "") if isinstance(body, dict) else ""
        ps = _get_ps()
        ps.set_config(plugin_name, config, bot_id)
        updated = ps.get_config(plugin_name, bot_id if bot_id else None)
        asyncio.ensure_future(_notify_agents_config_changed())
        return {"plugin": plugin_name, "bot_id": bot_id or "(global)", "config": updated}

    @app.put("/api/plugin/{plugin_name}/enabled")
    async def set_plugin_enabled(plugin_name: str, request: Request):
        body = await request.json()
        enabled = body.get("enabled", True)
        bot_id = body.get("bot_id", "")
        ps = _get_ps()
        ps.set_enabled(plugin_name, enabled, bot_id)
        asyncio.ensure_future(_notify_agents_config_changed())
        return {"plugin": plugin_name, "bot_id": bot_id or "(global)", "enabled": enabled}

    async def _notify_agents_config_changed():
        """Notify all online agents to re-sync plugin config. Jittered to avoid thundering herd."""
        import random, asyncio as _asyncio
        for agent in registry.list_agents():
            if agent["status"] != "online":
                continue
            # Jitter: 0-3s random delay per agent
            await _asyncio.sleep(random.uniform(0, 3))
            try:
                from agent.cluster.proxy import _get_client
                client = _get_client()
                await client.post(f"{agent['url']}/api/plugin/reload", timeout=5)
                logger.debug("Notified agent '%s' to reload plugins", agent["agent_id"])
            except Exception as exc:
                logger.debug("Failed to notify agent '%s': %s", agent["agent_id"], exc)

    # ── Start/Stop proxy ────────────────────────────────────────────────────

    @app.post("/api/startbot")
    async def proxy_startbot(request: Request):
        body = await request.json()
        bot_ids = body.get("bot_ids", [])
        if not bot_ids:
            raise HTTPException(status_code=400, detail="bot_ids required")

        # Pick an agent for new bots
        agent = registry.pick_agent()
        if not agent:
            raise HTTPException(status_code=503, detail="No online agent available")

        # Route and proxy
        for bid in bot_ids:
            registry.route_bot(bid, agent["agent_id"])

        return await proxy_http(request, agent["url"])

    @app.post("/api/stopbot")
    async def proxy_stopbot(request: Request):
        return await proxy_with_body_fallback(request)

    # ── WebSocket proxy ──────────────────────────────────────────────────────

    @app.websocket("/api/bot/{bot_id}/events")
    async def ws_proxy(ws: WebSocket, bot_id: str):
        route = registry.resolve_bot(bot_id)
        if not route:
            await ws.close(code=4004)
            return
        ws_path = f"/api/bot/{bot_id}/events"
        await proxy_ws(ws, route["url"], ws_path)

    # ── Web Console ──────────────────────────────────────────────────────────

    import os as _os
    _dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "static")
    _idx = _os.path.join(_dir, "index.html")
    if _os.path.isfile(_idx):
        from starlette.responses import FileResponse

        async def _console_auth(request: Request) -> bool:
            """Check console token if configured. Returns True if access granted."""
            if _console_token is None:
                return True
            token = request.query_params.get("token", "")
            return token == _console_token

        @app.get("/console", include_in_schema=False)
        async def _console(request: Request):
            if not await _console_auth(request):
                raise HTTPException(status_code=403, detail="Invalid or missing console token")
            return FileResponse(_idx)

        @app.get("/console/", include_in_schema=False)
        async def _console_slash(request: Request):
            if not await _console_auth(request):
                raise HTTPException(status_code=403, detail="Invalid or missing console token")
            return FileResponse(_idx)

        @app.get("/", include_in_schema=False)
        async def _root(request: Request):
            if not await _console_auth(request):
                raise HTTPException(status_code=403, detail="Invalid or missing console token")
            return FileResponse(_idx)

    # ── Catch-all proxy ─────────────────────────────────────────────────────

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def catch_all(path: str, request: Request):
        return await proxy_with_body_fallback(request)

    return app


# ── Re-exported from helpers (kept for backward compatibility) ───────────────

from agent.cluster.helpers import proxy_with_body_fallback, proxy_json as _proxy_json

_start_time = time.time()
