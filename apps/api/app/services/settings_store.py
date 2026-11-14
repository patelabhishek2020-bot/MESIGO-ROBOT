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


async def list_settings_meta(db: AsyncSession, category: Optional[str] = None) -> list[dict[str, Any]]:
    """Return metadata without decrypting secret values."""
    stmt = select(EncryptedSetting)
    if category:
        stmt = stmt.where(EncryptedSetting.category == category)
    result = await db.execute(stmt.order_by(EncryptedSetting.category, EncryptedSetting.key))
    rows = result.scalars().all()
    out: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = {
            "id": str(row.id),
            "category": row.category,
            "key": row.key,
            "is_secret": row.is_secret,
            "description": row.description,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        if not row.is_secret:
            item["value"] = decrypt_value(row.value_encrypted)
        else:
            item["value"] = "***"
        out.append(item)
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
