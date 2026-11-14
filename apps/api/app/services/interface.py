"""Voice + text interface endpoints support."""

import re
import uuid
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.brain import INTENT_ROUTES, brain
from app.models.operations import InterfaceSession

# Simple keyword → intent map for text/voice command parsing
KEYWORD_INTENTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(find|list|show)\s+leads?\b", re.I), "list_leads"),
    (re.compile(r"\bcreate\s+lead\b", re.I), "create_lead"),
    (re.compile(r"\bsend\s+(an?\s+)?email\b", re.I), "send_email"),
    (re.compile(r"\bsend\s+whatsapp\b", re.I), "send_whatsapp"),
    (re.compile(r"\b(find|list)\s+suppliers?\b", re.I), "list_suppliers"),
    (re.compile(r"\b(compare|get)\s+rates?\b", re.I), "compare_rates"),
    (re.compile(r"\bbook\s+shipment\b", re.I), "book_shipment"),
    (re.compile(r"\b(list|show)\s+shipments?\b", re.I), "list_shipments"),
    (re.compile(r"\bcreate\s+invoice\b", re.I), "create_invoice"),
    (re.compile(r"\bpay\s+invoice\b", re.I), "pay_invoice"),
    (re.compile(r"\bfinance\s+summary\b", re.I), "finance_summary"),
    (re.compile(r"\bcheck\s+compliance\b", re.I), "check_compliance"),
    (re.compile(r"\b(list|show)\s+documents?\b", re.I), "list_documents"),
    (re.compile(r"\bexpir(y|ation)\s+alerts?\b", re.I), "expiry_alerts"),
    (re.compile(r"\bstaff\s+panel\b", re.I), "staff_panel"),
    (re.compile(r"\blist\s+staff\b", re.I), "list_staff"),
    (re.compile(r"\bself[- ]?update\b", re.I), "propose_update"),
    (re.compile(r"\bdesign\s+(document|invoice)\b", re.I), "design_document"),
    (re.compile(r"\bpost\s+(to\s+)?social\b", re.I), "post_social"),
    (re.compile(r"\bowner\s+otp\b", re.I), "request_owner_otp"),
]


def parse_intent(text: str) -> tuple[Optional[str], dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return None, {}
    # Explicit "intent:name {...}" form
    if text.lower().startswith("intent:"):
        parts = text.split(maxsplit=1)
        intent = parts[0].split(":", 1)[1].strip()
        return intent if intent in INTENT_ROUTES else intent, {}
    for pattern, intent in KEYWORD_INTENTS:
        if pattern.search(text):
            return intent, {"utterance": text}
    return None, {"utterance": text}


async def get_or_create_session(
    db: AsyncSession,
    *,
    session_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    channel: str = "text",
) -> InterfaceSession:
    if session_id:
        row = (
            await db.execute(select(InterfaceSession).where(InterfaceSession.id == session_id))
        ).scalar_one_or_none()
        if row:
            return row
    session = InterfaceSession(id=uuid.uuid4(), user_id=user_id, channel=channel, transcript=[])
    db.add(session)
    await db.flush()
    return session


async def handle_text_turn(
    db: AsyncSession,
    *,
    text: str,
    user_id: Optional[UUID] = None,
    username: Optional[str] = None,
    session_id: Optional[UUID] = None,
    intent_override: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    session = await get_or_create_session(db, session_id=session_id, user_id=user_id, channel="text")
    intent, parsed_payload = parse_intent(text)
    if intent_override:
        intent = intent_override
    merged = {**parsed_payload, **(payload or {})}

    transcript = list(session.transcript or [])
    transcript.append({"role": "user", "text": text, "intent": intent})

    if not intent:
        reply = (
            "I could not map that to an agent intent. Try phrases like "
            "'list leads', 'send email', 'book shipment', or 'intent:list_leads'."
        )
        transcript.append({"role": "assistant", "text": reply})
        session.transcript = transcript
        await db.flush()
        return {
            "session_id": str(session.id),
            "intent": None,
            "reply": reply,
            "routed": False,
        }

    routed = await brain.route_intent(
        db,
        intent=intent,
        payload=merged,
        actor_user_id=user_id,
        actor_username=username,
    )
    reply = routed.get("message") or "Done."
    transcript.append({"role": "assistant", "text": reply, "result": {
        "success": routed.get("success"),
        "requires_approval": routed.get("requires_approval"),
        "executed": routed.get("executed"),
    }})
    session.transcript = transcript
    session.last_intent = intent
    await db.flush()
    return {
        "session_id": str(session.id),
        "intent": intent,
        "reply": reply,
        "routed": True,
        "result": routed,
    }


async def handle_voice_turn(
    db: AsyncSession,
    *,
    transcript_text: str,
    user_id: Optional[UUID] = None,
    username: Optional[str] = None,
    session_id: Optional[UUID] = None,
    payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Voice path: accepts STT transcript (Whisper integration hook).
    Audio bytes can be uploaded separately; this routes the transcript through the same brain.
    """
    session = await get_or_create_session(db, session_id=session_id, user_id=user_id, channel="voice")
    result = await handle_text_turn(
        db,
        text=transcript_text,
        user_id=user_id,
        username=username,
        session_id=session.id,
        payload=payload,
    )
    result["channel"] = "voice"
    result["stt"] = {"provider": "whisper_hook", "transcript": transcript_text}
    result["tts"] = {
        "provider": "tts_hook",
        "speak": result.get("reply"),
        "note": "TTS synthesis hook ready for pipeline wiring",
    }
    return result
