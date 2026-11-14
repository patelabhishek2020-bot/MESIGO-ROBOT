"""Agent 3 — Communication (Email, WhatsApp, WeChat, Phone/Twilio) + OTP-to-owner."""

import uuid
from typing import Any

from sqlalchemy import select

from app.agents.base import AgentResult, BaseAgent
from app.agents.helpers import require_db
from app.models.operations import MessageLog
from app.services.otp import create_owner_otp, verify_otp
from app.services.settings_store import get_setting


class CommunicationAgent(BaseAgent):
    agent_id = "communication"
    name = "Communication"
    description = "Email, WhatsApp, WeChat, Phone outreach and OTP-to-owner flow"
    status = "ready"
    capabilities = [
        "send_email",
        "send_whatsapp",
        "send_wechat",
        "call_contact",
        "send_sms",
        "request_owner_otp",
        "verify_owner_otp",
        "list_messages",
    ]

    async def handle(self, intent: str, payload: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        db = require_db(context)
        if intent == "send_email":
            return await self._send(db, channel="email", payload=payload)
        if intent == "send_whatsapp":
            return await self._send(db, channel="whatsapp", payload=payload)
        if intent == "send_wechat":
            return await self._send(db, channel="wechat", payload=payload)
        if intent == "send_sms":
            return await self._send(db, channel="sms", payload=payload)
        if intent == "call_contact":
            return await self._send(db, channel="voice", payload=payload)
        if intent == "request_owner_otp":
            otp = await create_owner_otp(
                db,
                purpose=payload.get("purpose", "approval"),
                channel=payload.get("channel", "whatsapp"),
                metadata=payload.get("metadata") or {},
            )
            return AgentResult(success=bool(otp.get("success")), message=otp.get("message", "OTP requested"), data=otp)
        if intent == "verify_owner_otp":
            if not payload.get("challenge_id") or not payload.get("code"):
                return AgentResult(success=False, message="challenge_id and code required")
            result = await verify_otp(db, uuid.UUID(str(payload["challenge_id"])), str(payload["code"]))
            return AgentResult(success=bool(result.get("success")), message=result.get("message", ""), data=result)
        if intent == "list_messages":
            return await self._list_messages(db, payload)
        return self.unsupported(intent)

    async def _send(self, db, *, channel: str, payload: dict[str, Any]) -> AgentResult:
        to_address = payload.get("to") or payload.get("to_address")
        if not to_address:
            return AgentResult(success=False, message="Recipient 'to' required")
        body = payload.get("body") or payload.get("message") or ""
        subject = payload.get("subject")

        creds_ok, provider = await self._channel_ready(db, channel)
        status = "queued_provider" if creds_ok else "queued_dry_run"
        log = MessageLog(
            id=uuid.uuid4(),
            channel=channel,
            direction="outbound",
            to_address=to_address,
            from_address=payload.get("from"),
            subject=subject,
            body_preview=(body[:500] if body else None),
            status=status,
            provider_ref=f"{provider}:{uuid.uuid4()}" if creds_ok else None,
            metadata_json={"dry_run": not creds_ok, "provider": provider},
        )
        db.add(log)
        await db.flush()
        return AgentResult(
            success=True,
            message=f"{channel} message {status}",
            data={
                "message_id": str(log.id),
                "channel": channel,
                "status": status,
                "dry_run": not creds_ok,
            },
            requires_approval=True,
            action_key=f"send_{channel}" if channel != "voice" else "call_contact",
        )

    async def _channel_ready(self, db, channel: str) -> tuple[bool, str]:
        if channel == "email":
            host = await get_setting(db, "email", "smtp_host")
            return bool(host), "smtp"
        if channel in ("whatsapp", "sms", "voice"):
            sid = await get_setting(db, "messaging", "twilio_account_sid")
            token = await get_setting(db, "messaging", "twilio_auth_token")
            return bool(sid and token), "twilio"
        if channel == "wechat":
            app_id = await get_setting(db, "messaging", "wechat_app_id")
            secret = await get_setting(db, "messaging", "wechat_app_secret")
            return bool(app_id and secret), "wechat"
        return False, "unknown"

    async def _list_messages(self, db, payload: dict[str, Any]) -> AgentResult:
        q = select(MessageLog).order_by(MessageLog.created_at.desc()).limit(int(payload.get("limit", 50)))
        if payload.get("channel"):
            q = q.where(MessageLog.channel == payload["channel"])
        rows = (await db.execute(q)).scalars().all()
        return AgentResult(
            success=True,
            message=f"{len(rows)} messages",
            data={
                "messages": [
                    {
                        "id": str(r.id),
                        "channel": r.channel,
                        "to": r.to_address,
                        "subject": r.subject,
                        "status": r.status,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in rows
                ]
            },
        )
