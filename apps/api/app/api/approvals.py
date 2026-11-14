"""Owner approval queue + OTP verification."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agents.brain import brain
from app.api.deps import CurrentUser, DbSession, OwnerUser
from app.services.approvals import decide_approval, list_pending
from app.services.audit import write_audit
from app.services.otp import create_owner_otp, verify_otp

router = APIRouter(prefix="/approvals", tags=["approvals"])


class DecideBody(BaseModel):
    approve: bool = True
    otp_code: Optional[str] = None
    note: Optional[str] = None
    execute: bool = True


class OtpRequest(BaseModel):
    channel: str = Field(default="whatsapp")
    purpose: str = Field(default="approval")


class OtpVerify(BaseModel):
    challenge_id: UUID
    code: str


@router.get("/pending")
async def pending(db: DbSession, user: CurrentUser, status: str = "pending"):
    return {"approvals": await list_pending(db, status=status)}


@router.post("/{approval_id}/decide")
async def decide(approval_id: UUID, body: DecideBody, db: DbSession, user: OwnerUser):
    decision = await decide_approval(
        db,
        approval_id=approval_id,
        approve=body.approve,
        decided_by=user.id,
        otp_code=body.otp_code,
        note=body.note,
    )
    await write_audit(
        db,
        action="approval.decide",
        actor_user_id=user.id,
        actor_username=user.username,
        resource_type="pending_approval",
        resource_id=str(approval_id),
        details={"approve": body.approve, "status": decision.get("status")},
        message=decision.get("message") or decision.get("status"),
    )
    if not decision.get("success"):
        return decision

    executed = None
    if body.approve and body.execute:
        executed = await brain.route_intent(
            db,
            intent=decision["intent"],
            payload=decision.get("payload") or {},
            actor_user_id=user.id,
            actor_username=user.username,
            preferred_agent=decision.get("agent_id"),
            force_execute=True,
        )
    return {"decision": decision, "execution": executed}


@router.post("/otp/request")
async def otp_request(body: OtpRequest, db: DbSession, user: OwnerUser):
    return await create_owner_otp(db, purpose=body.purpose, channel=body.channel)


@router.post("/otp/verify")
async def otp_verify(body: OtpVerify, db: DbSession, user: OwnerUser):
    return await verify_otp(db, body.challenge_id, body.code)
