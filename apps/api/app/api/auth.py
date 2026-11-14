"""Authentication + voice biometric enrollment hooks."""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, client_meta
from app.core.config import get_settings
from app.core.exceptions import MesigoError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, UserRole, VoiceBiometric
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
    UserOut,
    VoiceEnrollRequest,
    VoiceEnrollResponse,
)
from app.services.audit import write_audit
from app.services.settings_store import get_system_state

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    roles = []
    for ur in user.roles or []:
        if ur.role:
            roles.append(ur.role.name)
    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        is_owner=user.is_owner,
        must_change_password=user.must_change_password,
        roles=roles,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: DbSession):
    meta = client_meta(request)
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(User.username == body.username)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        await write_audit(
            db,
            action="auth.login.failed",
            actor_username=body.username,
            status="failed",
            **meta,
            message="Invalid credentials",
        )
        raise UnauthorizedError("Invalid username or password")

    user.last_login_at = datetime.now(timezone.utc)
    token = create_access_token(str(user.id), extra={"username": user.username, "is_owner": user.is_owner})
    wizard = await get_system_state(db, "setup_wizard")
    await write_audit(
        db,
        action="auth.login",
        actor_user_id=user.id,
        actor_username=user.username,
        **meta,
    )
    return TokenResponse(
        access_token=token,
        must_change_password=user.must_change_password,
        setup_required=not wizard.get("completed", False),
    )


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return _user_out(user)


@router.post("/change-password")
async def change_password(body: ChangePasswordRequest, user: CurrentUser, db: DbSession, request: Request):
    if not verify_password(body.current_password, user.hashed_password):
        raise UnauthorizedError("Current password incorrect")
    user.hashed_password = hash_password(body.new_password)
    user.must_change_password = False
    await write_audit(
        db,
        action="auth.password_changed",
        actor_user_id=user.id,
        actor_username=user.username,
        **client_meta(request),
    )
    return {"success": True, "message": "Password updated"}


@router.post("/voice/enroll", response_model=VoiceEnrollResponse)
async def enroll_voice(
    user: CurrentUser,
    db: DbSession,
    request: Request,
    file: UploadFile = File(...),
    label: str = "primary",
    enrollment_phrase: str = "Mesigo AI authorize my voice for business operations",
):
    """
    Voice biometric enrollment hook.
    Stores the sample and creates a biometric record; speaker-recognition model
    wiring is intentionally deferred (embedding_ref reserved).
    """
    settings = get_settings()
    voice_dir = Path(settings.voice_sample_dir) / str(user.id)
    voice_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "sample.wav").suffix or ".wav"
    sample_id = uuid.uuid4()
    sample_path = voice_dir / f"{sample_id}{ext}"
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise MesigoError("Voice sample too large (max 10MB)", code="payload_too_large", status_code=413)
    sample_path.write_bytes(content)

    record = VoiceBiometric(
        id=sample_id,
        user_id=user.id,
        label=label,
        sample_path=str(sample_path),
        embedding_ref=None,  # hook for future speaker recognition
        status="enrolled",
        enrollment_phrase=enrollment_phrase,
        enrolled_at=datetime.now(timezone.utc),
        metadata_json={"content_type": file.content_type, "bytes": len(content)},
    )
    db.add(record)
    await write_audit(
        db,
        action="auth.voice.enroll",
        actor_user_id=user.id,
        actor_username=user.username,
        resource_type="voice_biometric",
        resource_id=str(sample_id),
        **client_meta(request),
    )
    return VoiceEnrollResponse(
        id=record.id,
        status=record.status,
        label=record.label,
        enrollment_phrase=enrollment_phrase,
        sample_path=str(sample_path),
        message="Voice sample stored. Speaker recognition model hook ready for integration.",
    )


@router.post("/voice/enroll-meta", response_model=VoiceEnrollResponse)
async def enroll_voice_meta(body: VoiceEnrollRequest, user: CurrentUser, db: DbSession, request: Request):
    """Create a pending enrollment record without audio (wizard step placeholder)."""
    record = VoiceBiometric(
        id=uuid.uuid4(),
        user_id=user.id,
        label=body.label,
        status="pending",
        enrollment_phrase=body.enrollment_phrase,
        metadata_json={"source": "wizard_meta"},
    )
    db.add(record)
    await write_audit(
        db,
        action="auth.voice.enroll_meta",
        actor_user_id=user.id,
        actor_username=user.username,
        resource_type="voice_biometric",
        resource_id=str(record.id),
        **client_meta(request),
    )
    return VoiceEnrollResponse(
        id=record.id,
        status=record.status,
        label=record.label,
        enrollment_phrase=body.enrollment_phrase,
        message="Pending enrollment created — upload audio via /auth/voice/enroll",
    )


@router.get("/voice/status")
async def voice_status(user: CurrentUser, db: DbSession):
    result = await db.execute(
        select(VoiceBiometric).where(VoiceBiometric.user_id == user.id).order_by(VoiceBiometric.created_at.desc())
    )
    rows = result.scalars().all()
    return {
        "enrolled": any(r.status == "enrolled" for r in rows),
        "records": [
            {
                "id": str(r.id),
                "label": r.label,
                "status": r.status,
                "enrolled_at": r.enrolled_at.isoformat() if r.enrolled_at else None,
            }
            for r in rows
        ],
    }
