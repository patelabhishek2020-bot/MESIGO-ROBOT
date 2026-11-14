"""API subscription self-monitoring hooks."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.operations import ApiSubscriptionHealth
from app.services.settings_store import get_setting, list_settings_meta

logger = get_logger("api_monitor")

# provider -> (category, required setting keys as (category, key))
PROVIDER_CHECKS: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "llm": ("llm", [("llm", "api_key"), ("llm", "provider")]),
    "smtp": ("email", [("email", "smtp_host"), ("email", "smtp_user"), ("email", "smtp_password")]),
    "twilio": ("messaging", [("messaging", "twilio_account_sid"), ("messaging", "twilio_auth_token")]),
    "whatsapp": ("messaging", [("messaging", "whatsapp_business_token")]),
    "wechat": ("messaging", [("messaging", "wechat_app_id"), ("messaging", "wechat_app_secret")]),
    "logistics": ("logistics", [("banking_logistics", "logistics_api_key")]),
    "twitter": ("social", [("social", "twitter_api_key")]),
    "linkedin": ("social", [("social", "linkedin_access_token")]),
}


async def _upsert_health(
    db: AsyncSession,
    *,
    provider: str,
    category: str,
    status: str,
    error_message: str | None = None,
    metrics: dict[str, Any] | None = None,
) -> ApiSubscriptionHealth:
    result = await db.execute(select(ApiSubscriptionHealth).where(ApiSubscriptionHealth.provider == provider))
    row = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if not row:
        row = ApiSubscriptionHealth(provider=provider, category=category)
        db.add(row)
    row.category = category
    row.status = status
    row.last_checked_at = now
    row.error_message = error_message
    row.metrics = metrics or {}
    if status == "ok":
        row.last_success_at = now
        row.alert_sent = False
    await db.flush()
    return row


async def check_provider(db: AsyncSession, provider: str) -> dict[str, Any]:
    spec = PROVIDER_CHECKS.get(provider)
    if not spec:
        return {"provider": provider, "status": "unknown", "message": "No check defined"}
    category, keys = spec
    missing = []
    for cat, key in keys:
        val = await get_setting(db, cat, key)
        if not val:
            missing.append(f"{cat}.{key}")
    if missing:
        row = await _upsert_health(
            db,
            provider=provider,
            category=category,
            status="missing_creds",
            error_message=f"Missing: {', '.join(missing)}",
            metrics={"missing": missing},
        )
        return {
            "provider": provider,
            "status": row.status,
            "message": row.error_message,
            "id": str(row.id),
        }

    # Credentials present — mark ok (live ping hooks can extend per provider later)
    row = await _upsert_health(
        db,
        provider=provider,
        category=category,
        status="ok",
        metrics={"credential_check": "present"},
    )
    logger.info("api_check_ok", provider=provider)
    return {"provider": provider, "status": "ok", "id": str(row.id)}


async def check_all_providers(db: AsyncSession) -> dict[str, Any]:
    results = []
    for provider in PROVIDER_CHECKS:
        results.append(await check_provider(db, provider))
    degraded = [r for r in results if r["status"] != "ok"]
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "ok_count": len(results) - len(degraded),
        "issue_count": len(degraded),
        "results": results,
    }


async def list_health(db: AsyncSession) -> list[dict[str, Any]]:
    result = await db.execute(select(ApiSubscriptionHealth).order_by(ApiSubscriptionHealth.provider))
    rows = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "provider": r.provider,
            "category": r.category,
            "status": r.status,
            "last_checked_at": r.last_checked_at.isoformat() if r.last_checked_at else None,
            "last_success_at": r.last_success_at.isoformat() if r.last_success_at else None,
            "error_message": r.error_message,
            "metrics": r.metrics,
        }
        for r in rows
    ]


async def configured_integrations_summary(db: AsyncSession) -> dict[str, Any]:
    meta = await list_settings_meta(db)
    cats = sorted({m["category"] for m in meta})
    return {"configured_categories": cats, "setting_count": len(meta)}
