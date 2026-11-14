"""Shared helpers for agent handlers."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import MesigoError


def require_db(context: dict[str, Any]) -> AsyncSession:
    db = context.get("db")
    if db is None:
        raise MesigoError("Agent context missing database session", code="agent_context", status_code=500)
    return db


def actor_uuid(context: dict[str, Any]):
    from uuid import UUID

    raw = context.get("actor_user_id")
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except ValueError:
        return None
