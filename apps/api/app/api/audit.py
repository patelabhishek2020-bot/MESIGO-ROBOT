"""Audit log listing."""

from typing import Optional

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.audit import AuditLog

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs")
async def list_logs(
    db: DbSession,
    user: CurrentUser,
    limit: int = 100,
    action: Optional[str] = None,
    status: Optional[str] = None,
):
    limit = min(max(limit, 1), 500)
    q = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if action:
        q = q.where(AuditLog.action == action)
    if status:
        q = q.where(AuditLog.status == status)
    rows = (await db.execute(q)).scalars().all()
    return {
        "logs": [
            {
                "id": str(r.id),
                "action": r.action,
                "actor_username": r.actor_username,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "status": r.status,
                "message": r.message,
                "details": r.details,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }
