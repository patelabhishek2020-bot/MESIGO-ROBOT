"""Encrypted settings store — Setup Wizard source of truth."""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_value, encrypt_value
from app.models.settings import EncryptedSetting, SystemState


async def upsert_setting(
    db: AsyncSession,
    *,
    category: str,
    key: str,
    value: str,
    is_secret: bool = True,
    description: Optional[str] = None,
    updated_by: Optional[UUID] = None,
) -> EncryptedSetting:
    result = await db.execute(
        select(EncryptedSetting).where(
            EncryptedSetting.category == category,
            EncryptedSetting.key == key,
        )
    )
    row = result.scalar_one_or_none()
    encrypted = encrypt_value(value)
    if row:
        row.value_encrypted = encrypted
        row.is_secret = is_secret
        if description is not None:
            row.description = description
        row.updated_by = updated_by
        await db.flush()
        return row

    row = EncryptedSetting(
        category=category,
        key=key,
        value_encrypted=encrypted,
        is_secret=is_secret,
        description=description,
        updated_by=updated_by,
    )
    db.add(row)
    await db.flush()
    return row


async def get_setting(db: AsyncSession, category: str, key: str) -> Optional[str]:
    result = await db.execute(
        select(EncryptedSetting).where(
            EncryptedSetting.category == category,
            EncryptedSetting.key == key,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    return decrypt_value(row.value_encrypted)


def mask_secret(value: str) -> str:
    """Show that a secret is saved without revealing it (e.g. sk-…xxxx)."""
    if not value:
        return ""
    if len(value) <= 8:
        return "••••••••"
    prefix = value[:4]
    suffix = value[-4:]
    return f"{prefix}…{suffix}"


def is_masked_secret(value: str) -> bool:
    """True when the client submitted a masked placeholder (keep existing)."""
    if value is None:
        return False
    v = str(value).strip()
    if not v:
        return False
    if v in {"***", "••••", "••••••••", "****", "[saved]"}:
        return True
    if "…" in v or "..." in v:
        return True
    if set(v) <= {"•", "*", "·", "."}:
        return True
    return False


async def list_settings_meta(db: AsyncSession, category: Optional[str] = None) -> list[dict[str, Any]]:
    """Return settings for UI hydration — secrets masked, non-secrets plaintext."""
    stmt = select(EncryptedSetting)
    if category:
        stmt = stmt.where(EncryptedSetting.category == category)
    result = await db.execute(stmt.order_by(EncryptedSetting.category, EncryptedSetting.key))
    rows = result.scalars().all()
    out: list[dict[str, Any]] = []
    for row in rows:
        plaintext = decrypt_value(row.value_encrypted)
        item: dict[str, Any] = {
            "id": str(row.id),
            "category": row.category,
            "key": row.key,
            "is_secret": row.is_secret,
            "description": row.description,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "has_value": bool(plaintext),
        }
        if not row.is_secret:
            item["value"] = plaintext
            item["masked"] = False
        else:
            item["value"] = mask_secret(plaintext)
            item["masked"] = True
        out.append(item)
    return out


async def settings_map(
    db: AsyncSession, category: str, *, mask_secrets: bool = True
) -> dict[str, Any]:
    """Category → {key: value} for wizard hydration."""
    meta = await list_settings_meta(db, category)
    out: dict[str, Any] = {}
    for item in meta:
        out[item["key"]] = item["value"]
        if item.get("masked"):
            out[f"{item['key']}__masked"] = True
            out[f"{item['key']}__has_value"] = item.get("has_value", False)
    return out


async def get_system_state(db: AsyncSession, key: str) -> dict[str, Any]:
    result = await db.execute(select(SystemState).where(SystemState.key == key))
    row = result.scalar_one_or_none()
    return row.value_json if row else {}


async def set_system_state(db: AsyncSession, key: str, value: dict[str, Any]) -> SystemState:
    result = await db.execute(select(SystemState).where(SystemState.key == key))
    row = result.scalar_one_or_none()
    if row:
        row.value_json = value
        await db.flush()
        return row
    row = SystemState(key=key, value_json=value)
    db.add(row)
    await db.flush()
    return row
