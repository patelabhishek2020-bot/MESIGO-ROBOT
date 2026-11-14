"""API subscription self-monitoring."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession, OwnerUser
from app.services.api_monitor import (
    check_all_providers,
    check_provider,
    configured_integrations_summary,
    list_health,
)
from app.services.audit import write_audit

router = APIRouter(prefix="/monitor", tags=["api-monitor"])


@router.get("/health")
async def health(db: DbSession, user: CurrentUser):
    return {"subscriptions": await list_health(db), "summary": await configured_integrations_summary(db)}


@router.post("/check")
async def check_all(db: DbSession, user: OwnerUser):
    result = await check_all_providers(db)
    await write_audit(
        db,
        action="monitor.check_all",
        actor_user_id=user.id,
        actor_username=user.username,
        details={"issue_count": result["issue_count"]},
    )
    return result


@router.post("/check/{provider}")
async def check_one(provider: str, db: DbSession, user: OwnerUser):
    result = await check_provider(db, provider)
    await write_audit(
        db,
        action="monitor.check",
        actor_user_id=user.id,
        actor_username=user.username,
        resource_type="api_provider",
        resource_id=provider,
        details=result,
    )
    return result
