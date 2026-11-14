"""OTP-to-owner approval flow."""

import asyncio
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
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
    force_dry_run: bool = False,
) -> dict[str, Any]:
    """
    Generate OTP, store hash, and deliver via configured channel.
    SMTP is attempted when Wizard email settings exist; otherwise dry-run
    (returns ``dev_code`` so owners/tests can complete the approval loop).
    Twilio provider hooks stay dry-run until a real SDK send is wired.
    ``force_dry_run`` skips provider send (used by automated tests).
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

    delivery = await _deliver_otp(
        db,
        channel=channel,
        destination=dest,
        code=code,
        challenge_id=challenge.id,
        force_dry_run=force_dry_run,
    )

    logger.info("otp_created", challenge_id=str(challenge.id), channel=channel, dry_run=delivery.get("dry_run"))
    return {
        "success": True,
        "challenge_id": str(challenge.id),
        "channel": channel,
        "destination_masked": challenge.destination_masked,
        "expires_at": challenge.expires_at.isoformat(),
        "delivery": delivery,
        # Only return code when delivery was dry-run (no provider send succeeded).
        "dev_code": code if delivery.get("dry_run") else None,
    }


def _smtp_send_sync(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
    use_tls: bool,
) -> None:
    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    if port == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, timeout=30, context=context) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
        return

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        if use_tls or port == 587:
            context = ssl.create_default_context()
            smtp.starttls(context=context)
        smtp.login(user, password)
        smtp.send_message(msg)


async def _try_smtp_deliver(db: AsyncSession, *, destination: str, code: str) -> dict[str, Any]:
    host = await get_setting(db, "email", "smtp_host")
    user = await get_setting(db, "email", "smtp_user")
    password = await get_setting(db, "email", "smtp_password")
    from_email = await get_setting(db, "email", "from_email")
    port_raw = await get_setting(db, "email", "smtp_port")
    use_tls_raw = await get_setting(db, "email", "use_tls")
    if not host or not user or not password or not from_email:
        return {"ok": False, "reason": "incomplete_smtp_settings"}
    try:
        port = int(port_raw or 587)
    except (TypeError, ValueError):
        port = 587
    use_tls = str(use_tls_raw or "true").lower() in {"1", "true", "yes", "on"}
    body = f"Mesigo AI owner OTP: {code}. Valid for approval confirmation."
    try:
        await asyncio.to_thread(
            _smtp_send_sync,
            host=host,
            port=port,
            user=user,
            password=password,
            from_email=from_email,
            to_email=destination,
            subject="Mesigo AI OTP",
            body=body,
            use_tls=use_tls,
        )
        return {"ok": True, "provider_ref": f"smtp:{host}:{port}"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("otp_smtp_failed", error=str(exc)[:200])
        return {"ok": False, "reason": f"smtp_error:{type(exc).__name__}"}


async def _deliver_otp(
    db: AsyncSession,
    *,
    channel: str,
    destination: str,
    code: str,
    challenge_id: UUID,
    force_dry_run: bool = False,
) -> dict[str, Any]:
    body = f"Mesigo AI owner OTP: {code}. Valid for approval confirmation."
    twilio_sid = await get_setting(db, "messaging", "twilio_account_sid")
    twilio_token = await get_setting(db, "messaging", "twilio_auth_token")

    dry_run = True
    provider_ref = None
    status = "queued_dry_run"
    delivery_note = None

    if force_dry_run:
        dry_run = True
        status = "queued_dry_run"
        delivery_note = "forced_dry_run"
        provider_ref = f"dry-run:{challenge_id}"
    elif channel == "email":
        sent = await _try_smtp_deliver(db, destination=destination, code=code)
        if sent.get("ok"):
            dry_run = False
            status = "sent"
            provider_ref = sent.get("provider_ref") or f"smtp:{challenge_id}"
        else:
            # Incomplete SMTP or send failure → dry-run so owner/tests can still approve
            dry_run = True
            status = "queued_dry_run"
            delivery_note = sent.get("reason")
            provider_ref = f"smtp-dry-run:{challenge_id}"
    elif channel in ("whatsapp", "sms", "voice") and twilio_sid and twilio_token:
        # Twilio SDK send not wired yet — stay dry-run (do not pretend a message was sent).
        dry_run = True
        status = "queued_dry_run"
        delivery_note = "twilio_sdk_not_wired"
        provider_ref = f"twilio-dry-run:{channel}:{challenge_id}"

    log = MessageLog(
        channel=channel,
        direction="outbound",
        to_address=_mask(destination),
        subject="Mesigo AI OTP",
        body_preview=body.replace(code, "******"),
        status=status,
        provider_ref=provider_ref,
        metadata_json={
            "kind": "otp",
            "challenge_id": str(challenge_id),
            "dry_run": dry_run,
            "note": delivery_note,
        },
    )
    db.add(log)
    await db.flush()
    return {
        "status": status,
        "dry_run": dry_run,
        "message_log_id": str(log.id),
        "provider_ref": provider_ref,
        "note": delivery_note,
    }


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
