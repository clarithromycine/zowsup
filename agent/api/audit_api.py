"""Audit log API — query HTTP access records."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from pydantic import BaseModel

from agent.manager.audit_store import get_default as _get_audit_store

logger = logging.getLogger(__name__)
router = APIRouter(tags=["audit"])


class AuditEntry(BaseModel):
    id: int
    timestamp: float
    method: str
    path: str
    source_ip: str
    bot_id: str
    status: int
    duration_ms: int


@router.get("/api/audit", response_model=list[AuditEntry])
async def list_audit(
    limit: int = Query(200, ge=1, le=2000, description="Max records to return"),
    bot_id: str | None = Query(None, description="Filter by bot_id"),
    path: str | None = Query(None, description="Filter by path prefix"),
    before: float | None = Query(None, description="Cursor: timestamp before which to fetch"),
):
    """Return recent API audit records, newest first."""
    return _get_audit_store().query(
        limit=limit,
        bot_id=bot_id,
        path_prefix=path,
        before_ts=before,
    )
