"""
FastAPI application with ACCESSKEY authentication.

Start:  python -m agent [--accesskey KEY]
"""

from __future__ import annotations

import os
import sys

# Ensure project root on path for imports from sibling packages
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query, WebSocket, WebSocketException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRouter

from agent.schemas import HealthResponse

# ── Access Key ───────────────────────────────────────────────────────────────

_access_key: Optional[str] = None  # Set at startup from CLI args


def set_access_key(key: Optional[str]) -> None:
    """Configure the access key for this agent instance.

    Args:
        key: The access key string, or None to disable authentication.
    """
    global _access_key
    _access_key = key


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

    account_store.start()
    log_broadcaster.start()
    bot_manager.start_periodic_flush(interval=600.0)

    from agent.api.bot_api import router as bot_router
    from agent.api.cmd_api import router as cmd_router
    from agent.api.msg_api import router as msg_router
    from agent.api.log_api import router as log_router
    app.include_router(bot_router)
    app.include_router(cmd_router)
    app.include_router(msg_router)
    app.include_router(log_router)

    import logging
    logging.getLogger('transitions').setLevel(logging.WARNING)

    yield


# ── App Factory ──────────────────────────────────────────────────────────────

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
            thread_count=threading.active_count(),
            db_bot_count=len(account_store.list_all()),
            running_bot_count=running,
            memory_bytes=mem,
            cpu_time_seconds=cpu_time,
        )

    app.include_router(api_router)

    return app
