"""Pending approval queue + OTP-gated owner decisions."""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operations import PendingApproval
from app.services.otp import create_owner_otp, verify_otp


async def create_pending_approval(
    db: AsyncSession,
    *,
    action_key: str,
    agent_id: str,
    intent: str,
    payload: dict[str, Any],
    requested_by: Optional[UUID] = None,
    send_otp: bool = True,
    otp_channel: str = "whatsapp",
    force_otp_dry_run: bool = False,
) -> dict[str, Any]:
    approval = PendingApproval(
        action_key=action_key,
        agent_id=agent_id,
        intent=intent,
        payload=payload,
        status="pending",
        requested_by=requested_by,
    )
    db.add(approval)
    await db.flush()

    otp_info = None
    if send_otp:
        otp_info = await create_owner_otp(
            db,
            purpose="approval",
            channel=otp_channel,
            related_approval_id=approval.id,
            metadata={"action_key": action_key, "agent_id": agent_id, "intent": intent},
            force_dry_run=force_otp_dry_run or bool(payload.get("otp_dry_run")),
        )
        if otp_info.get("challenge_id"):
            approval.otp_challenge_id = UUID(otp_info["challenge_id"])
            await db.flush()

    return {
        "approval_id": str(approval.id),
        "status": approval.status,
        "action_key": action_key,
        "agent_id": agent_id,
        "intent": intent,
        "otp": otp_info,
    }


async def decide_approval(
    db: AsyncSession,
    *,
    approval_id: UUID,
    approve: bool,
    decided_by: Optional[UUID] = None,
    otp_code: Optional[str] = None,
    note: Optional[str] = None,
) -> dict[str, Any]:
    result = await db.execute(select(PendingApproval).where(PendingApproval.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        return {"success": False, "message": "Approval not found"}
    if approval.status != "pending":
        return {"success": False, "message": f"Approval already {approval.status}"}

    if approval.otp_challenge_id:
        if not otp_code:
            return {"success": False, "message": "OTP code required for this approval"}
        verified = await verify_otp(db, approval.otp_challenge_id, otp_code)
        if not verified.get("success"):
            return verified

    approval.status = "approved" if approve else "rejected"
    approval.decided_by = decided_by
    approval.decision_note = note
    approval.decided_at = datetime.now(timezone.utc)
    await db.flush()
    return {
        "success": True,
        "approval_id": str(approval.id),
        "status": approval.status,
        "payload": approval.payload,
        "agent_id": approval.agent_id,
        "intent": approval.intent,
    }


async def list_pending(db: AsyncSession, status: str = "pending") -> list[dict[str, Any]]:
    result = await db.execute(
        select(PendingApproval)
        .where(PendingApproval.status == status)
        .order_by(PendingApproval.created_at.desc())
        .limit(100)
    )
    rows = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "action_key": r.action_key,
            "agent_id": r.agent_id,
            "intent": r.intent,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "payload": r.payload,
        }
        for r in rows
    ]
