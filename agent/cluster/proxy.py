"""
HTTP + WebSocket proxy middleware for the Router.

Routes requests to the target agent based on bot_id extracted from the
request path, query params, or body.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from fastapi import Request, WebSocket, WebSocketDisconnect
from starlette.responses import Response
from starlette.websockets import WebSocketState

from agent.cluster.registry import registry

logger = logging.getLogger(__name__)

# ── Bot ID extraction ────────────────────────────────────────────────────────

_BOT_ID_PATTERNS = [
    # /api/bot/{bot_id}/...
    lambda path: path.split("/")[3] if path.startswith("/api/bot/") and len(path.split("/")) >= 4 else None,
    # /api/conversation/{bot_id}:...
    lambda path: path.split("/")[3].split(":")[0] if path.startswith("/api/conversation/") and len(path.split("/")) >= 4 else None,
    # /api/escalation?bot_id=...
    lambda path, qp: qp.get("bot_id"),
]


def _extract_bot_id(request: Request) -> str | None:
    """Extract bot_id from the incoming request.

    Strategy (ordered):
      1. Path: /api/bot/{bot_id}/...
      2. Path: /api/conversation/{bot_id}:...
      3. Query: ?bot_id=...
      4. JSON body: {"bot_id": "..."} (for POST/PUT)
    """
    path = request.url.path
    qp = request.query_params

    # Pattern-based extraction
    for pattern in _BOT_ID_PATTERNS:
        try:
            result = pattern(path, qp) if pattern.__code__.co_argcount >= 2 else pattern(path)
            if result:
                return result
        except Exception:
            continue

    return None


async def _extract_bot_id_from_body(request: Request) -> str | None:
    """Try to extract bot_id from JSON body (for POST/PUT sendmsg, startbot, etc.)."""
    if request.method not in ("POST", "PUT"):
        return None
    try:
        body = await request.json()
        return body.get("bot_id") or body.get("botId")
    except Exception:
        return None


# ── HTTP Proxy ───────────────────────────────────────────────────────────────

async def proxy_http(request: Request, target_url: str) -> Response:
    """Forward an HTTP request to the target agent and return its response."""
    client = _get_client()
    try:
        body = await request.body()
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ("host", "content-length")
        }
        resp = await client.request(
            method=request.method,
            url=f"{target_url}{request.url.path}?{request.url.query}".rstrip("?"),
            headers=headers,
            content=body,
            timeout=30,
        )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers),
        )
    except httpx.TimeoutException:
        return Response(content='{"detail":"upstream timeout"}', status_code=504, media_type="application/json")
    except httpx.ConnectError:
        return Response(content='{"detail":"upstream unreachable"}', status_code=502, media_type="application/json")
    except Exception as exc:
        logger.warning("Proxy error to %s: %s", target_url, exc)
        return Response(content='{"detail":"proxy error"}', status_code=502, media_type="application/json")


# ── Scatter-Gather ───────────────────────────────────────────────────────────

async def scatter_gather(path: str, query: str = "") -> list[dict]:
    """GET a path from ALL online agents and aggregate results."""
    client = _get_client()
    agents = registry.list_agents()
    results = []
    for agent in agents:
        if agent["status"] != "online":
            continue
        try:
            url = f"{agent['url']}{path}?{query}".rstrip("?")
            resp = await client.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    results.extend(data)
                elif isinstance(data, dict):
                    results.append(data)
        except Exception as exc:
            logger.debug("scatter_gather failed for %s: %s", agent["agent_id"], exc)
    return results


# ── WebSocket Proxy ──────────────────────────────────────────────────────────

async def proxy_ws(client_ws: WebSocket, target_url: str, path: str) -> None:
    """Bidirectional WebSocket proxy between client and target agent.

    Uses websockets library to connect to upstream, then relays
    messages in both directions via asyncio tasks.
    """
    await client_ws.accept()

    ws_url = target_url.replace("http://", "ws://").replace("https://", "wss://") + path
    try:
        import websockets
        async with websockets.connect(ws_url) as upstream:
            async def client_to_upstream():
                while True:
                    try:
                        data = await client_ws.receive_text()
                        await upstream.send(data)
                    except Exception:
                        break

            async def upstream_to_client():
                while True:
                    try:
                        data = await upstream.recv()
                        await client_ws.send_text(data)
                    except Exception:
                        break

            done, pending = await asyncio.wait(
                [asyncio.ensure_future(client_to_upstream()),
                 asyncio.ensure_future(upstream_to_client())],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
    except ImportError:
        logger.warning("websockets library not installed, WS proxy unavailable; install: pip install websockets")
        try:
            await client_ws.send_text('{"error":"websockets library not installed on cluster"}')
        except Exception:
            pass
    except Exception as exc:
        logger.debug("WS proxy error: %s", exc)
    finally:
        try:
            await client_ws.close()
        except Exception:
            pass


# ── HTTP client pool ─────────────────────────────────────────────────────────

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
    return _client


async def close_client():
    global _client
    if _client:
        await _client.aclose()
        _client = None
