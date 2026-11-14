"""Agent 9 — HR & Office + Staff Panel."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.agents.base import AgentResult, BaseAgent
from app.agents.helpers import require_db
from app.models.operations import AttendanceLog, StaffMember


class HrOfficeAgent(BaseAgent):
    agent_id = "hr_office"
    name = "HR & Office + Staff Panel"
    description = "Staff roles, attendance, office ops"
    status = "ready"
    capabilities = [
        "hr_action",
        "add_staff",
        "list_staff",
        "attendance_checkin",
        "attendance_checkout",
        "list_attendance",
        "staff_panel",
    ]

    async def handle(self, intent: str, payload: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        db = require_db(context)
        if intent in ("add_staff", "hr_action") and payload.get("action", "add_staff") in ("add_staff", "hire"):
            return await self._add_staff(db, payload)
        if intent == "add_staff":
            return await self._add_staff(db, payload)
        if intent in ("list_staff", "staff_panel"):
            return await self._list_staff(db, payload)
        if intent == "attendance_checkin":
            return await self._attendance(db, payload, "check_in")
        if intent == "attendance_checkout":
            return await self._attendance(db, payload, "check_out")
        if intent == "list_attendance":
            return await self._list_attendance(db, payload)
        if intent == "hr_action":
            action = payload.get("action", "list_staff")
            return await self.handle(action, payload, context)
        return self.unsupported(intent)

    async def _add_staff(self, db, payload: dict[str, Any]) -> AgentResult:
        if not payload.get("full_name"):
            return AgentResult(success=False, message="full_name required")
        member = StaffMember(
            id=uuid.uuid4(),
            user_id=uuid.UUID(str(payload["user_id"])) if payload.get("user_id") else None,
            full_name=payload["full_name"],
            department=payload.get("department"),
            title=payload.get("title"),
            email=payload.get("email"),
            phone=payload.get("phone"),
            status=payload.get("status", "active"),
            hire_date=datetime.now(timezone.utc),
        )
        db.add(member)
        await db.flush()
        return AgentResult(
            success=True,
            message=f"Staff added: {member.full_name}",
            data={"staff_id": str(member.id)},
            requires_approval=True,
            action_key="hire_staff",
        )

    async def _list_staff(self, db, payload: dict[str, Any]) -> AgentResult:
        q = select(StaffMember).order_by(StaffMember.created_at.desc()).limit(int(payload.get("limit", 100)))
        if payload.get("status"):
            q = q.where(StaffMember.status == payload["status"])
        rows = (await db.execute(q)).scalars().all()
        return AgentResult(
            success=True,
            message=f"{len(rows)} staff",
            data={
                "staff": [
                    {
                        "id": str(r.id),
                        "full_name": r.full_name,
                        "department": r.department,
                        "title": r.title,
                        "email": r.email,
                        "status": r.status,
                    }
                    for r in rows
                ]
            },
        )

    async def _attendance(self, db, payload: dict[str, Any], event_type: str) -> AgentResult:
        staff_id = payload.get("staff_id")
        if not staff_id:
            return AgentResult(success=False, message="staff_id required")
        member = (
            await db.execute(select(StaffMember).where(StaffMember.id == uuid.UUID(str(staff_id))))
        ).scalar_one_or_none()
        if not member:
            return AgentResult(success=False, message="Staff not found")
        log = AttendanceLog(
            id=uuid.uuid4(),
            staff_id=member.id,
            event_type=event_type,
            note=payload.get("note"),
        )
        db.add(log)
        await db.flush()
        return AgentResult(
            success=True,
            message=f"{member.full_name} {event_type}",
            data={"attendance_id": str(log.id), "staff_id": str(member.id), "event_type": event_type},
        )

    async def _list_attendance(self, db, payload: dict[str, Any]) -> AgentResult:
        q = select(AttendanceLog).order_by(AttendanceLog.occurred_at.desc()).limit(int(payload.get("limit", 100)))
        if payload.get("staff_id"):
            q = q.where(AttendanceLog.staff_id == uuid.UUID(str(payload["staff_id"])))
        rows = (await db.execute(q)).scalars().all()
        return AgentResult(
            success=True,
            message=f"{len(rows)} attendance events",
            data={
                "events": [
                    {
                        "id": str(r.id),
                        "staff_id": str(r.staff_id),
                        "event_type": r.event_type,
                        "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
                    }
                    for r in rows
                ]
            },
        )
