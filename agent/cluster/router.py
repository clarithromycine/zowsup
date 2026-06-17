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
from urllib.parse import urlparse

from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketException, Header, Depends, Query
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


# ── Helper: port extraction ─────────────────────────────────────────────────

def _extract_port(url: str) -> int | None:
    """Extract port number from URL, or None if not present."""
    try:
        port = urlparse(url).port
        return port if port else None
    except Exception:
        return None


# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    registry.start()

    # ── Cluster audit ──────────────────────────────────────────────────
    from agent.manager.audit_store import AuditStore, set_default as _set_audit
    cluster_audit = AuditStore(db_name="cluster_audit.db")
    cluster_audit.start()
    _set_audit(cluster_audit)

    health_task = asyncio.ensure_future(_health_check_loop())
    logger.info("Cluster started")
    yield
    health_task.cancel()
    from agent.cluster.proxy import close_client
    await close_client()
    logger.info("Cluster stopped")


# ── Health checker ───────────────────────────────────────────────────────────

async def _health_check_loop(interval: float = 30.0):
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

    # ── Audit middleware (cluster records all proxied requests w/ real client IP) ──
    import uuid as _uuid
    _AUDIT_SKIP = ("/api/health", "/api/cluster/health", "/api/audit", "/console", "/static", "/ws")

    @app.middleware("http")
    async def _cluster_audit(request: Request, call_next):
        t0 = time.time()
        response = await call_next(request)
        elapsed = time.time() - t0
        path = request.url.path
        if not any(path.startswith(p) for p in _AUDIT_SKIP):
            try:
                from agent.manager.audit_store import get_default as _gs
                bot_id = ""
                parts = path.split("/")
                if len(parts) >= 4 and parts[1] == "api" and parts[2] == "bot":
                    bot_id = parts[3]
                elif "bot_id" in request.query_params:
                    bot_id = request.query_params.get("bot_id", "")
                source_ip = request.client.host if request.client else ""
                _gs().record(
                    method=request.method,
                    path=path,
                    source_ip=source_ip,
                    bot_id=bot_id,
                    status=response.status_code,
                    duration_ms=int(elapsed * 1000),
                )
            except Exception:
                pass
        return response

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
        agent_url = body.get("url", "")
        if not agent_id:
            raise HTTPException(status_code=400, detail="agent_id required")

        # ── Always use the real client IP from the HTTP request, not what
        #     the agent advertises (which may be a hostname, .local, or loopback).
        #     Only the port is taken from the agent's URL. ──
        client_ip = request.client.host if request.client else "unknown"
        port = _extract_port(agent_url) or 8000
        url = f"http://{client_ip}:{port}"

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
        # Auto-re-register if agent was lost (e.g. cluster restart)
        if not registry.heartbeat(agent_id):
            # Re-register with the real client IP as URL
            client_ip = request.client.host if request.client else "unknown"
            url = body.get("url") or f"http://{client_ip}:8000"
            registry.register_agent(agent_id, url)
            registry.heartbeat(agent_id)
        return {"ok": True}

    @cluster_router.post("/api/cluster/migrate")
    async def _migrate_bot(request: Request):
        """Automated bot migration between agents.
        Flow: stop → export from source → import to target → start → update route.
        """
        from agent.cluster.migrate import migrate_bot
        return await migrate_bot(request)

    @cluster_router.get("/api/cluster/migrate/status")
    async def _migrate_status(bot_id: str | None = Query(None)):
        """Get migration status for a specific bot or all ongoing migrations."""
        from agent.cluster.migrate import get_migration_status
        return get_migration_status(bot_id)

    @cluster_router.post("/api/cluster/deploybot")
    async def deploy_bot(request: Request):
        """Deploy bot(s) to the least-loaded agent in the cluster.

        Accepts the same JSON body as Agent's POST /api/importbot
        ({accounts: [{data: "phone,cc,...", env: "android"}, ...]}),
        picks the best agent, forwards the import, and starts all
        successfully imported bots.

        Naming: `deploybot` (not `importbot`) to distinguish the cluster-level
        "pick agent and distribute" responsibility from the agent-level "parse
        CSV and store locally" responsibility.
        """
        body = await request.json()
        accounts = body.get("accounts", [])
        if not accounts:
            raise HTTPException(status_code=400, detail="accounts list required")

        # Pick the least-loaded online agent
        agent = registry.pick_agent()
        if not agent:
            raise HTTPException(status_code=503, detail="No online agent available")

        # Capacity check
        current_bots = len(registry.list_bot_routes(agent["agent_id"]))
        new_bots = len(accounts)
        if current_bots + new_bots > registry.MAX_BOTS_PER_AGENT:
            raise HTTPException(
                status_code=429,
                detail=f"Target agent '{agent['agent_id']}' would exceed capacity "
                       f"({current_bots + new_bots} > {registry.MAX_BOTS_PER_AGENT})",
            )

        # Forward import to the agent
        from agent.cluster.proxy import _get_client
        client = _get_client()
        resp = await client.post(
            f"{agent['url']}/api/importbot",
            json={"accounts": accounts},
            timeout=60,
        )
        if resp.status_code != 200:
            detail = ""
            try:
                detail = resp.json().get("detail", resp.text[:200])
            except Exception:
                detail = resp.text[:200]
            raise HTTPException(status_code=resp.status_code, detail=f"Agent import failed: {detail}")

        import_result = resp.json()
        success_count = import_result.get("success_count", 0)
        results = import_result.get("results", [])

        if success_count == 0:
            return {
                "deployed_to": agent["agent_id"],
                "success_count": 0,
                "results": results,
            }

        # Start successfully imported bots on the agent
        imported_ids = [r["bot_id"] for r in results if r.get("status") == "STOPPED"]
        if imported_ids:
            start_resp = await client.post(
                f"{agent['url']}/api/startbot",
                json={"bot_ids": imported_ids, "mode": "fire"},
                timeout=30,
            )
            if start_resp.status_code == 200:
                start_data = start_resp.json()
                # Route each started bot to this agent
                for r in start_data.get("results", []):
                    if r.get("status") != "ERROR":
                        registry.route_bot(r["bot_id"], agent["agent_id"])

        return {
            "deployed_to": agent["agent_id"],
            "success_count": success_count,
            "results": results,
        }

    @cluster_router.post("/api/cluster/agents/{agent_id}/scan")
    async def agent_scan(agent_id: str):
        """Trigger a directory re-scan on a specific agent to rebuild its account DB."""
        agent = registry.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        from agent.cluster.proxy import _get_client
        client = _get_client()
        resp = await client.post(f"{agent['url']}/api/scan", timeout=30)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text[:200])
        return resp.json()

    # Register cluster management routes (all guarded by _check_cluster_secret)
    app.include_router(cluster_router)

    # ── Aggregate endpoints ──────────────────────────────────────────────────

    @app.get("/api/listbot")
    async def list_bots(
        agent_id: str | None = Query(None, description="Filter by agent_id"),
        bot_id: str | None = Query(None, description="Filter by bot_id (substring match)"),
    ):
        """Aggregate bots from all (or filtered) agents, tagging each with its agent_id."""
        agents = registry.list_agents()
        if agent_id:
            agents = [a for a in agents if a["agent_id"] == agent_id]
        results = []
        for agent in agents:
            if agent["status"] != "online":
                continue
            try:
                from agent.cluster.proxy import _get_client
                client = _get_client()
                url = f"{agent['url']}/api/listbot"
                if bot_id:
                    url += f"?bot_id={bot_id}"
                resp = await client.get(url, timeout=10)
                if resp.status_code == 200:
                    bots = resp.json()
                    if isinstance(bots, list):
                        for b in bots:
                            b["agent_id"] = agent["agent_id"]
                        results.extend(bots)
            except Exception as exc:
                logger.debug("listbot failed for %s: %s", agent["agent_id"], exc)
        # Sort: RUNNING first, then by started_at descending
        results.sort(key=lambda b: (0 if b.get("status") == "RUNNING" else 1,
                                     -(b.get("started_at") or 0)))
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

    @app.get("/api/cluster/health")
    async def cluster_health_aggregate():
        """Aggregate health from all online agents. Returns per-agent status
        plus cluster-wide totals."""
        agents = registry.list_agents()
        online_agents = [a for a in agents if a["status"] == "online"]
        per_agent = []
        total_bots = 0
        total_db_bots = 0

        from agent.cluster.proxy import _get_client
        client = _get_client()
        for agent in online_agents:
            try:
                resp = await client.get(f"{agent['url']}/api/health", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    data["agent_id"] = agent["agent_id"]
                    per_agent.append(data)
                    total_bots += data.get("running_bots", 0)
                    total_db_bots += data.get("db_bot_count", 0)
            except Exception:
                per_agent.append({
                    "agent_id": agent["agent_id"],
                    "status": "unreachable",
                })

        return {
            "status": "ok",
            "version": "cluster-0.1.0",
            "uptime_seconds": int(time.time() - _start_time),
            "agents_total": len(agents),
            "agents_online": len(online_agents),
            "total_running_bots": total_bots,
            "total_db_bots": total_db_bots,
            "agents": per_agent,
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
        """List conversations: route by bot_id if provided, otherwise
        scatter to all online agents, merge results, and dedup by id."""
        bot_id = request.query_params.get("bot_id")
        if bot_id:
            route = registry.resolve_bot(bot_id)
            if route:
                return await proxy_http(request, route["url"])
            raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not routed")

        # Scatter-gather with dedup
        from agent.cluster.proxy import _get_client
        client = _get_client()
        seen: set[str] = set()
        merged: list[dict] = []
        query_str = str(request.url.query) if request.url.query else ""

        for agent in registry.list_agents():
            if agent["status"] != "online":
                continue
            try:
                url = f"{agent['url']}/api/conversation"
                if query_str:
                    url += f"?{query_str}"
                resp = await client.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        cid = item.get("id") or item.get("conversation_id", "")
                        if cid and cid not in seen:
                            seen.add(cid)
                            item["agent_id"] = agent["agent_id"]
                            merged.append(item)
            except Exception as exc:
                logger.debug("conversation scatter failed for %s: %s", agent["agent_id"], exc)
        return merged

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
            # Forward a system note to the agent that owns the conversation
            esc = _get_esc().get(esc_id)
            if esc:
                conv_id = esc.get("conversation_id", "")
                bot_id2 = conv_id.split(":")[0] if ":" in conv_id else ""
                route = registry.resolve_bot(bot_id2) if bot_id2 else None
                if route:
                    try:
                        from agent.cluster.proxy import _get_client
                        client = _get_client()
                        await client.post(
                            f"{route['url']}/api/conversation/{conv_id}/note",
                            json={"content": "✅ Escalation resolved"},
                            timeout=5,
                        )
                    except Exception:
                        pass
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

        # Every bot is already routed to a single agent (set at import/registration).
        # Use the first bot's agent as the target; complain if any bot is unrouted.
        target_url: str | None = None
        missing: list[str] = []

        for bid in bot_ids:
            route = registry.resolve_bot(bid)
            if route:
                if target_url is None:
                    target_url = route["url"]
            else:
                missing.append(bid)

        if target_url is None:
            raise HTTPException(status_code=404, detail=f"No bots routed: {missing}")

        # Proxy to the owning agent
        from agent.cluster.proxy import _get_client
        client = _get_client()

        # If there are unrouted bots, still send the routed ones; include errors for missing
        if missing:
            resp = await proxy_http(request, target_url)
            data = resp.json() if hasattr(resp, 'json') else {}
            # Can't easily inject into proxied response — just log
            logger.warning("startbot: %d bots not routed, only sending %d to %s",
                           len(missing), len(bot_ids) - len(missing), target_url)

        return await proxy_http(request, target_url)

    @app.post("/api/stopbot")
    async def proxy_stopbot(request: Request):
        body = await request.json()
        bot_ids = body.get("bot_ids", [])
        if not bot_ids:
            raise HTTPException(status_code=400, detail="bot_ids required")

        # Use the first routed bot's agent as the target
        target_url: str | None = None
        for bid in bot_ids:
            route = registry.resolve_bot(bid)
            if route:
                target_url = route["url"]
                break

        if target_url is None:
            raise HTTPException(status_code=404, detail="No bots routed to any agent")

        return await proxy_http(request, target_url)

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

    # ── Audit API (must be before catch-all) ────────────────────────────────
    from agent.api.audit_api import router as audit_router
    app.include_router(audit_router)

    # ── Catch-all proxy ─────────────────────────────────────────────────────

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def catch_all(path: str, request: Request):
        return await proxy_with_body_fallback(request)

    return app


# ── Re-exported from helpers (kept for backward compatibility) ───────────────

from agent.cluster.helpers import proxy_with_body_fallback, proxy_json as _proxy_json

_start_time = time.time()
