"""
Survey API — query satisfaction survey results.

GET  /api/survey?bot_id=&status=    — list survey sessions
GET  /api/survey/{id}              — detail
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from agent.plugin.satisfaction.store import survey_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/survey", tags=["survey"])


@router.get("")
async def list_surveys(
    bot_id: str | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
):
    """List survey sessions, optionally filtered by bot_id and/or status."""
    items = survey_store.list(bot_id=bot_id, status=status, limit=limit)
    return items


@router.get("/{session_id}")
async def get_survey(session_id: str):
    """Get a single survey session by ID."""
    item = survey_store.get(session_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Survey session '{session_id}' not found")
    return item
