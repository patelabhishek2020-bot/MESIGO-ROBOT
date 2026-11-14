"""Health, readiness, and system info."""

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.config import get_settings
from app.services.settings_store import get_system_state

router = APIRouter(tags=["system"])


@router.get("/health")
async def health():
    return {"status": "ok", "service": "mesigo-api"}


@router.get("/ready")
async def ready(db: DbSession):
    await db.execute(text("SELECT 1"))
    wizard = await get_system_state(db, "setup_wizard")
    settings = get_settings()
    return {
        "status": "ready",
        "database": "ok",
        "environment": settings.environment,
        "setup_completed": bool(wizard.get("completed")),
    }


@router.get("/api/v1/system/info")
async def system_info(db: DbSession):
    settings = get_settings()
    wizard = await get_system_state(db, "setup_wizard")
    return {
        "app": settings.app_name,
        "version": "0.1.0",
        "environment": settings.environment,
        "setup_completed": bool(wizard.get("completed")),
        "agents": 12,
        "note": "Owner credentials live in Setup Wizard encrypted settings — not .env",
    }
