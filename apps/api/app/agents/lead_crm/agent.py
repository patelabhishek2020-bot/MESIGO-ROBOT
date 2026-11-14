"""Agent 2 — Lead Generation & CRM."""

import uuid
from typing import Any

from sqlalchemy import or_, select

from app.agents.base import AgentResult, BaseAgent
from app.agents.helpers import require_db
from app.models.crm import Contact, Lead


class LeadCrmAgent(BaseAgent):
    agent_id = "lead_crm"
    name = "Lead Generation & CRM"
    description = "Find, qualify, and manage leads and contacts"
    status = "ready"
    capabilities = [
        "find_leads",
        "create_lead",
        "update_lead",
        "list_leads",
        "manage_crm",
        "create_contact",
        "list_contacts",
        "qualify_lead",
    ]

    async def handle(self, intent: str, payload: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        db = require_db(context)
        if intent in ("create_lead", "find_leads") and payload.get("create"):
            return await self._create_lead(db, payload)
        if intent == "create_lead":
            return await self._create_lead(db, payload)
        if intent in ("list_leads", "find_leads", "manage_crm"):
            return await self._list_leads(db, payload)
        if intent == "update_lead" or intent == "qualify_lead":
            return await self._update_lead(db, payload, qualify=(intent == "qualify_lead"))
        if intent == "create_contact":
            return await self._create_contact(db, payload)
        if intent == "list_contacts":
            return await self._list_contacts(db, payload)
        return self.unsupported(intent)

    async def _create_lead(self, db, payload: dict[str, Any]) -> AgentResult:
        lead = Lead(
            id=uuid.uuid4(),
            company_name=payload.get("company_name"),
            contact_name=payload.get("contact_name"),
            email=payload.get("email"),
            phone=payload.get("phone"),
            country=payload.get("country"),
            source=payload.get("source", "manual"),
            status=payload.get("status", "new"),
            notes=payload.get("notes"),
            metadata_json=payload.get("metadata") or {},
        )
        db.add(lead)
        await db.flush()
        return AgentResult(
            success=True,
            message=f"Lead created: {lead.company_name or lead.contact_name or lead.id}",
            data={"lead_id": str(lead.id), "status": lead.status},
        )

    async def _list_leads(self, db, payload: dict[str, Any]) -> AgentResult:
        q = select(Lead).order_by(Lead.created_at.desc()).limit(int(payload.get("limit", 50)))
        if payload.get("status"):
            q = q.where(Lead.status == payload["status"])
        if payload.get("query"):
            term = f"%{payload['query']}%"
            q = q.where(
                or_(
                    Lead.company_name.ilike(term),
                    Lead.contact_name.ilike(term),
                    Lead.email.ilike(term),
                )
            )
        rows = (await db.execute(q)).scalars().all()
        return AgentResult(
            success=True,
            message=f"Found {len(rows)} leads",
            data={
                "leads": [
                    {
                        "id": str(r.id),
                        "company_name": r.company_name,
                        "contact_name": r.contact_name,
                        "email": r.email,
                        "country": r.country,
                        "status": r.status,
                        "source": r.source,
                    }
                    for r in rows
                ]
            },
        )

    async def _update_lead(self, db, payload: dict[str, Any], qualify: bool = False) -> AgentResult:
        lead_id = payload.get("lead_id")
        if not lead_id:
            return AgentResult(success=False, message="lead_id required")
        lead = (
            await db.execute(select(Lead).where(Lead.id == uuid.UUID(str(lead_id))))
        ).scalar_one_or_none()
        if not lead:
            return AgentResult(success=False, message="Lead not found")
        for field in ("company_name", "contact_name", "email", "phone", "country", "notes", "source"):
            if field in payload:
                setattr(lead, field, payload[field])
        if qualify:
            lead.status = payload.get("status", "qualified")
        elif "status" in payload:
            lead.status = payload["status"]
        await db.flush()
        return AgentResult(
            success=True,
            message=f"Lead updated ({lead.status})",
            data={"lead_id": str(lead.id), "status": lead.status},
        )

    async def _create_contact(self, db, payload: dict[str, Any]) -> AgentResult:
        if not payload.get("full_name"):
            return AgentResult(success=False, message="full_name required")
        contact = Contact(
            id=uuid.uuid4(),
            lead_id=uuid.UUID(str(payload["lead_id"])) if payload.get("lead_id") else None,
            full_name=payload["full_name"],
            email=payload.get("email"),
            phone=payload.get("phone"),
            whatsapp=payload.get("whatsapp"),
            wechat_id=payload.get("wechat_id"),
            company_name=payload.get("company_name"),
            role_title=payload.get("role_title"),
            tags=payload.get("tags") or [],
        )
        db.add(contact)
        await db.flush()
        return AgentResult(
            success=True,
            message=f"Contact created: {contact.full_name}",
            data={"contact_id": str(contact.id)},
        )

    async def _list_contacts(self, db, payload: dict[str, Any]) -> AgentResult:
        q = select(Contact).order_by(Contact.created_at.desc()).limit(int(payload.get("limit", 50)))
        rows = (await db.execute(q)).scalars().all()
        return AgentResult(
            success=True,
            message=f"Found {len(rows)} contacts",
            data={
                "contacts": [
                    {
                        "id": str(r.id),
                        "full_name": r.full_name,
                        "email": r.email,
                        "phone": r.phone,
                        "company_name": r.company_name,
                    }
                    for r in rows
                ]
            },
        )
