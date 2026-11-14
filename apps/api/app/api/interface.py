"""Voice + text owner/staff interface."""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.exceptions import MesigoError
from app.services.audit import write_audit
from app.services.interface import handle_text_turn, handle_voice_turn

router = APIRouter(prefix="/interface", tags=["voice-text-interface"])


class TextTurn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    session_id: Optional[UUID] = None
    intent: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)


class VoiceTranscriptTurn(BaseModel):
    transcript: str = Field(min_length=1, max_length=8000)
    session_id: Optional[UUID] = None
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/text")
async def text_turn(body: TextTurn, db: DbSession, user: CurrentUser):
    result = await handle_text_turn(
        db,
        text=body.text,
        user_id=user.id,
        username=user.username,
        session_id=body.session_id,
        intent_override=body.intent,
        payload=body.payload,
    )
    await write_audit(
        db,
        action="interface.text",
        actor_user_id=user.id,
        actor_username=user.username,
        details={"intent": result.get("intent"), "session_id": result.get("session_id")},
        message=result.get("reply"),
    )
    return result


@router.post("/voice/transcript")
async def voice_transcript(body: VoiceTranscriptTurn, db: DbSession, user: CurrentUser):
    result = await handle_voice_turn(
        db,
        transcript_text=body.transcript,
        user_id=user.id,
        username=user.username,
        session_id=body.session_id,
        payload=body.payload,
    )
    await write_audit(
        db,
        action="interface.voice",
        actor_user_id=user.id,
        actor_username=user.username,
        details={"intent": result.get("intent"), "session_id": result.get("session_id")},
        message=result.get("reply"),
    )
    return result


@router.post("/voice/audio")
async def voice_audio(
    db: DbSession,
    user: CurrentUser,
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
):
    """
    Accept audio for Whisper STT hook. Stores sample and expects client to also
    post transcript, or future worker to transcribe asynchronously.
    """
    settings = get_settings()
    from pathlib import Path
    import uuid as uuid_lib

    content = await file.read()
    if len(content) > 15 * 1024 * 1024:
        raise MesigoError("Audio too large (max 15MB)", code="payload_too_large", status_code=413)
    voice_dir = Path(settings.voice_sample_dir) / "interface" / str(user.id)
    voice_dir.mkdir(parents=True, exist_ok=True)
    path = voice_dir / f"{uuid_lib.uuid4()}.webm"
    path.write_bytes(content)
    await write_audit(
        db,
        action="interface.voice.audio",
        actor_user_id=user.id,
        actor_username=user.username,
        details={"bytes": len(content), "path": str(path)},
    )
    return {
        "success": True,
        "audio_path": str(path),
        "stt": {
            "provider": "whisper_hook",
            "status": "accepted",
            "message": "Audio stored. Post /interface/voice/transcript with STT text, or wire Whisper worker.",
        },
        "session_id": session_id,
    }
