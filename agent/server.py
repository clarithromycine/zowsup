"""
FastAPI application with ACCESSKEY authentication.

Start:  python -m agent [--accesskey KEY]
"""

from __future__ import annotations

import logging
import os
import sys
import time
import uuid

# Ensure project root on path for imports from sibling packages
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRouter

from agent.schemas import HealthResponse

logger = logging.getLogger(__name__)

# ── Server start time ────────────────────────────────────────────────────────

_start_time = time.time()

# ── WebSocket connection counter ─────────────────────────────────────────────

_ws_connection_count = 0

def ws_connected():
    global _ws_connection_count
    _ws_connection_count += 1

def ws_disconnected():
    global _ws_connection_count
    _ws_connection_count = max(0, _ws_connection_count - 1)

# ── Access Key ───────────────────────────────────────────────────────────────

_access_key: Optional[str] = None  # Set at startup from CLI args
_agent_id: str = ""  # Set at startup from CLI/env
_agent_port: int | None = None  # Set from CLI --port for cluster self-URL
_agent_host: str = "127.0.0.1"  # Advertised host for cluster registration (env: CLUSTER_ADVERTISE_HOST)
_cluster_mode: bool = False  # True when CLUSTER_URL env is set — audit is handled by Cluster
_audit_store = None  # type: AuditStore | None — created in lifespan, used by middleware


def set_access_key(key: Optional[str]) -> None:
    """Configure the access key for this agent instance.

    Args:
        key: The access key string, or None to disable authentication.
    """
    global _access_key
    _access_key = key


def set_agent_id(agent_id: str) -> None:
    """Set the agent identifier for multi-agent routing."""
    global _agent_id
    _agent_id = agent_id


def set_agent_port(port: int) -> None:
    """Set the agent port for cluster self-URL."""
    global _agent_port
    _agent_port = port


def set_agent_host(host: str) -> None:
    """Set the advertised host for cluster registration.

    If the bound host is 0.0.0.0, the real hostname/IP should be resolved
    by the caller (or overridden via CLUSTER_ADVERTISE_HOST env var).
    """
    global _agent_host
    _agent_host = host


def _check_rest_access_key(x_access_key: Optional[str] = Header(None)) -> None:
    """FastAPI dependency: verify X-Access-Key header against configured key.

    Raises HTTPException(403) if the key is required but missing/wrong.
    """
    if _access_key is None:
        return  # Auth disabled
    if x_access_key != _access_key:
        raise HTTPException(status_code=403, detail="Invalid or missing access key")


async def _check_ws_access_key(
    websocket: WebSocket,
    access_key: Optional[str] = Query(None),
) -> bool:
    """Verify WebSocket access_key query parameter.

    Returns True if access is granted, False if denied.
    Caller must close the WebSocket with 4003 on denial.
    """
    if _access_key is None:
        return True
    return access_key == _access_key


# ── Shared Router with auth dependency ───────────────────────────────────────

# All REST API routes use this router so auth is applied uniformly.
api_router = APIRouter(dependencies=[Depends(_check_rest_access_key)])


# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup only. Shutdown handled by signal handler in __main__.py."""
    from agent.manager.log_broadcaster import log_broadcaster
    from agent.manager.account_store import account_store
    from agent.manager.bot_manager import bot_manager
    from agent.manager.conversation_store import conv_store

    account_store.start(agent_id=_agent_id)
    log_broadcaster.start()
    conv_store.start()
    bot_manager.start_periodic_flush(interval=600.0)

    # ── Audit: only active in standalone mode (cluster handles its own) ──
    global _cluster_mode, _audit_store
    _cluster_mode = bool(os.environ.get("CLUSTER_URL", ""))
    if not _cluster_mode:
        from agent.manager.audit_store import AuditStore, set_default as _set_audit
        _audit_store = AuditStore(db_name="agent_audit.db")
        _audit_store.start()
        _set_audit(_audit_store)

    from agent.plugin.store import plugin_store as _plugin_store
    from agent.plugin.manager import plugin_manager as _plugin_manager
    from agent.manager.escalation_queue import escalation_queue as _escalation_queue
    _plugin_store.start()
    _escalation_queue.start()

    from agent.plugin.ai import AIPlugin
    from agent.plugin.translation import TranslationPlugin
    _plugin_manager.register(TranslationPlugin())
    _plugin_manager.register(AIPlugin())
    _plugin_store.set_config("translation", {"work_lang":"zh","target_lang":"en","provider":"google"})
    _plugin_store.set_enabled("translation", True)

    from agent.api.bot_api import router as bot_router
    from agent.api.cmd_api import router as cmd_router
    from agent.api.msg_api import router as msg_router
    from agent.api.log_api import router as log_router
    from agent.api.conversation_api import router as conv_router
    from agent.api.plugin_api import router as plugin_router
    from agent.api.escalation_api import router as escalation_router
    from agent.api.migrate_api import router as migrate_router
    from agent.api.audit_api import router as audit_router
    app.include_router(bot_router)
    app.include_router(cmd_router)
    app.include_router(msg_router)
    app.include_router(log_router)
    app.include_router(conv_router)
    app.include_router(plugin_router)
    app.include_router(escalation_router)
    app.include_router(migrate_router)
    app.include_router(audit_router)

    import logging
    logging.getLogger('transitions').setLevel(logging.WARNING)

    # ── Cluster auto-registration ────────────────────────────────────────────
    cluster_url = os.environ.get("CLUSTER_URL", "")
    if cluster_url:
        import asyncio, httpx
        agent_id = _agent_id
        own_port = _agent_port or 8000
        own_url = f"http://{_agent_host}:{own_port}"
        cluster_secret = os.environ.get("CLUSTER_SECRET", "")
        _cluster_headers = {"X-Cluster-Secret": cluster_secret} if cluster_secret else {}

        # Register
        try:
            from agent.manager.bot_manager import bot_manager
            bots = [info.bot_id for info in bot_manager.list_bots()]
            async with httpx.AsyncClient(timeout=httpx.Timeout(10)) as client:
                resp = await client.post(
                    f"{cluster_url}/api/cluster/agents",
                    json={"agent_id": agent_id, "url": own_url, "bots": bots},
                    headers=_cluster_headers,
                )
                if resp.status_code == 200:
                    print(f"[Agent] Registered with cluster {cluster_url} as '{agent_id}'")
                elif resp.status_code == 403:
                    print(f"[Agent] Cluster rejected registration (403) — check CLUSTER_SECRET")

            # Sync plugin config from Router
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(10)) as client:
                    sync_resp = await client.get(f"{cluster_url}/api/plugin/sync")
                    if sync_resp.status_code == 200:
                        rows = sync_resp.json()
                        if isinstance(rows, list) and rows:
                            _plugin_store.import_from(rows)
                            print(f"[Agent] Synced {len(rows)} plugin configs from cluster")
            except Exception as e:
                print(f"[Agent] Plugin sync skipped: {e}")
        except Exception as e:
            print(f"[Agent] Cluster unreachable ({cluster_url}): {e}")

        # Heartbeat task
        async def _heartbeat():
            while True:
                await asyncio.sleep(60)
                try:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(10)) as c:
                        bots = [info.bot_id for info in bot_manager.list_bots()]
                        await c.post(
                            f"{cluster_url}/api/cluster/agents/{agent_id}/heartbeat",
                            json={"bots": bots, "url": own_url},
                            headers=_cluster_headers,
                        )
                except Exception:
                    pass
        heartbeat_task = asyncio.ensure_future(_heartbeat())

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    if cluster_url:
        heartbeat_task.cancel()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10)) as c:
                await c.delete(
                    f"{cluster_url}/api/cluster/agents/{_agent_id}",
                    headers=_cluster_headers,
                )
                print(f"[Agent] Deregistered from cluster")
        except Exception:
            pass


def create_app() -> FastAPI:
    """Build and return the FastAPI application instance."""
    app = FastAPI(
        title="Zowsup Agent",
        description="Multi-bot WhatsApp protocol management API",
        version="0.9.0",
        lifespan=lifespan,
    )

    # ── Inject X-Access-Key security scheme into OpenAPI (Swagger UI "Authorize" button) ──
    # We do this by overriding openapi() rather than using Depends(APIKeyHeader),
    # because a global dependency would break WebSocket routes.
    _original_openapi = app.openapi

    def _custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = _original_openapi()
        schema.setdefault("components", {})["securitySchemes"] = {
            "X-Access-Key": {
                "type": "apiKey",
                "in": "header",
                "name": "X-Access-Key",
                "description": "Enter the access key configured via --accesskey",
            }
        }
        # Apply to all REST operations (not WebSocket, but doesn't matter for docs)
        schema.setdefault("security", []).append({"X-Access-Key": []})
        app.openapi_schema = schema
        return schema

    app.openapi = _custom_openapi

    # CORS: allow all origins by default (configurable later)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── X-Request-ID + Slow Request tracking + Audit log ──
    _AUDIT_SKIP_PREFIXES = ("/api/health", "/api/audit", "/console", "/static", "/ws")

    @app.middleware("http")
    async def request_tracker(request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        t0 = time.time()
        response = await call_next(request)
        elapsed = time.time() - t0
        response.headers["X-Request-ID"] = req_id
        if elapsed > 5.0:
            logger.warning(f"[{req_id}] {request.method} {request.url.path} took {elapsed:.1f}s")

        # Audit log (only in standalone mode; cluster handles its own)
        path = request.url.path
        if not _cluster_mode and not any(path.startswith(p) for p in _AUDIT_SKIP_PREFIXES):
            try:
                # Extract bot_id from path: /api/bot/{bot_id}/... or query param
                bot_id = ""
                parts = path.split("/")
                if len(parts) >= 4 and parts[1] == "api" and parts[2] == "bot":
                    bot_id = parts[3]
                elif "bot_id" in request.query_params:
                    bot_id = request.query_params.get("bot_id", "")
                source_ip = request.client.host if request.client else ""
                _audit_store.record(
                    method=request.method,
                    path=path,
                    source_ip=source_ip,
                    bot_id=bot_id,
                    status=response.status_code,
                    duration_ms=int(elapsed * 1000),
                )
            except Exception:
                pass  # Never let audit logging break the request
        return response

    # Health check (uses api_router for auth)
    @api_router.get("/api/health", response_model=HealthResponse)
    async def health():
        import threading
        from agent.manager.bot_manager import bot_manager
        from agent.manager.account_store import account_store

        running = sum(1 for b in bot_manager._bots.values() if b.thread and b.thread.is_alive())

        # Memory / CPU — psutil preferred, fall back to resource/os
        mem = 0
        cpu_time = 0.0
        try:
            import psutil
            proc = psutil.Process()
            mem = proc.memory_info().rss
            cpu_time = sum(proc.cpu_times()[:2])
        except ImportError:
            try:
                import resource
                usage = resource.getrusage(resource.RUSAGE_SELF)
                cpu_time = usage.ru_utime + usage.ru_stime
                mem = usage.ru_maxrss
            except ImportError:
                import os
                t = os.times()
                cpu_time = t.user + t.system

        return HealthResponse(
            status="ok",
            version=app.version,
            uptime_seconds=int(time.time() - _start_time),
            thread_count=threading.active_count(),
            db_bot_count=len(account_store.list_all()),
            running_bot_count=running,
            ws_connections=_ws_connection_count,
            memory_bytes=mem,
            cpu_time_seconds=cpu_time,
        )

    # Web console: http://host:port/console
    import os as _os
    _dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "static")
    _idx = _os.path.join(_dir, "index.html")
    if _os.path.isfile(_idx):
        from starlette.responses import FileResponse
        @app.get("/console", include_in_schema=False)
        async def _console(): return FileResponse(_idx)
        @app.get("/console/", include_in_schema=False)
        async def _console_slash(): return FileResponse(_idx)
        @app.get("/", include_in_schema=False)
        async def _root(): return FileResponse(_idx)

    app.include_router(api_router)

    return app
