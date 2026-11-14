"""OTP-to-owner approval flow."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import hash_password, verify_password
from app.models.operations import MessageLog, OtpChallenge
from app.services.settings_store import get_setting

logger = get_logger("otp")


def _mask(dest: str) -> str:
    if "@" in dest:
        name, domain = dest.split("@", 1)
        return f"{name[:2]}***@{domain}"
    digits = "".join(c for c in dest if c.isdigit())
    if len(digits) < 4:
        return "***"
    return f"+***{digits[-4:]}"


async def resolve_owner_destinations(db: AsyncSession) -> dict[str, Optional[str]]:
    phones = await get_setting(db, "owner_phones", "phones")
    primary = await get_setting(db, "owner_phones", "primary_phone")
    email = await get_setting(db, "email", "from_email")
    phone = primary or (phones.split(",")[0].strip() if phones else None)
    return {"phone": phone, "email": email}


async def create_owner_otp(
    db: AsyncSession,
    *,
    purpose: str = "approval",
    channel: str = "whatsapp",
    related_approval_id: Optional[UUID] = None,
    ttl_minutes: int = 10,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Generate OTP, store hash, and queue delivery via configured channel.
    Actual Twilio/SMTP send uses wizard credentials when present; otherwise dry-run.
    """
    destinations = await resolve_owner_destinations(db)
    if channel in ("whatsapp", "sms", "voice"):
        dest = destinations.get("phone")
        if not dest:
            channel = "email"
            dest = destinations.get("email")
    else:
        dest = destinations.get("email") or destinations.get("phone")
        channel = "email" if destinations.get("email") else "sms"

    if not dest:
        return {
            "success": False,
            "message": "No owner phone/email configured in Setup Wizard",
        }

    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge = OtpChallenge(
        purpose=purpose,
        channel=channel,
        destination_masked=_mask(dest),
        code_hash=hash_password(code),
        related_approval_id=related_approval_id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
        metadata_json=metadata or {},
        status="sent",
    )
    db.add(challenge)
    await db.flush()

    delivery = await _deliver_otp(db, channel=channel, destination=dest, code=code, challenge_id=challenge.id)

    logger.info("otp_created", challenge_id=str(challenge.id), channel=channel, dry_run=delivery.get("dry_run"))
    return {
        "success": True,
        "challenge_id": str(challenge.id),
        "channel": channel,
        "destination_masked": challenge.destination_masked,
        "expires_at": challenge.expires_at.isoformat(),
        "delivery": delivery,
        # Never return code in production responses — only for dry-run diagnostics
        "dev_code": code if delivery.get("dry_run") else None,
    }


async def _deliver_otp(
    db: AsyncSession,
    *,
    channel: str,
    destination: str,
    code: str,
    challenge_id: UUID,
) -> dict[str, Any]:
    body = f"Mesigo AI owner OTP: {code}. Valid for approval confirmation."
    twilio_sid = await get_setting(db, "messaging", "twilio_account_sid")
    twilio_token = await get_setting(db, "messaging", "twilio_auth_token")
    smtp_host = await get_setting(db, "email", "smtp_host")

    dry_run = True
    provider_ref = None
    status = "queued_dry_run"

    if channel in ("whatsapp", "sms", "voice") and twilio_sid and twilio_token:
        # Real Twilio call deferred to provider SDK; mark ready-to-send
        dry_run = False
        status = "queued_provider"
        provider_ref = f"twilio:{channel}:{challenge_id}"
    elif channel == "email" and smtp_host:
        dry_run = False
        status = "queued_provider"
        provider_ref = f"smtp:{challenge_id}"

    log = MessageLog(
        channel=channel,
        direction="outbound",
        to_address=_mask(destination),
        subject="Mesigo AI OTP",
        body_preview=body.replace(code, "******"),
        status=status,
        provider_ref=provider_ref,
        metadata_json={"kind": "otp", "challenge_id": str(challenge_id), "dry_run": dry_run},
    )
    db.add(log)
    await db.flush()
    return {"status": status, "dry_run": dry_run, "message_log_id": str(log.id), "provider_ref": provider_ref}


async def verify_otp(db: AsyncSession, challenge_id: UUID, code: str) -> dict[str, Any]:
    result = await db.execute(select(OtpChallenge).where(OtpChallenge.id == challenge_id))
    challenge = result.scalar_one_or_none()
    if not challenge:
        return {"success": False, "message": "OTP challenge not found"}
    if challenge.status == "verified":
        return {"success": True, "message": "Already verified", "challenge_id": str(challenge.id)}
    if challenge.expires_at < datetime.now(timezone.utc):
        challenge.status = "expired"
        return {"success": False, "message": "OTP expired"}
    if challenge.attempts >= challenge.max_attempts:
        challenge.status = "failed"
        return {"success": False, "message": "Too many attempts"}

    challenge.attempts += 1
    if not verify_password(code, challenge.code_hash):
        return {"success": False, "message": "Invalid OTP", "attempts": challenge.attempts}

    challenge.status = "verified"
    challenge.verified_at = datetime.now(timezone.utc)
    await db.flush()
    return {"success": True, "message": "OTP verified", "challenge_id": str(challenge.id)}
