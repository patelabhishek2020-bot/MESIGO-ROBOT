"""Central AI Brain — Master Orchestrator."""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.registry import get_agent, list_agents
from app.core.logging import get_logger
from app.models.settings import ApprovalRule
from app.services.approvals import create_pending_approval
from app.services.audit import write_audit

logger = get_logger("brain")

INTENT_ROUTES: dict[str, str] = {
    # Lead / CRM
    "find_leads": "lead_crm",
    "create_lead": "lead_crm",
    "update_lead": "lead_crm",
    "list_leads": "lead_crm",
    "manage_crm": "lead_crm",
    "create_contact": "lead_crm",
    "list_contacts": "lead_crm",
    "qualify_lead": "lead_crm",
    # Communication
    "send_email": "communication",
    "send_whatsapp": "communication",
    "send_wechat": "communication",
    "send_sms": "communication",
    "call_contact": "communication",
    "request_owner_otp": "communication",
    "verify_owner_otp": "communication",
    "list_messages": "communication",
    # Supplier
    "find_supplier": "supplier_rate",
    "create_supplier": "supplier_rate",
    "list_suppliers": "supplier_rate",
    "get_rate": "supplier_rate",
    "add_rate": "supplier_rate",
    "compare_rates": "supplier_rate",
    # Logistics
    "book_shipment": "logistics",
    "create_shipment": "logistics",
    "update_shipment": "logistics",
    "list_shipments": "logistics",
    "prepare_docs": "logistics",
    "shipment_status": "logistics",
    # Finance
    "pay_invoice": "finance",
    "create_invoice": "finance",
    "list_invoices": "finance",
    "mark_paid": "finance",
    "finance_summary": "finance",
    # Compliance
    "check_compliance": "compliance",
    "list_rules": "compliance",
    "add_rule": "compliance",
    "seed_rules": "compliance",
    "list_checks": "compliance",
    "file_compliance": "compliance",
    # Documents
    "store_document": "document_vault",
    "retrieve_document": "document_vault",
    "list_documents": "document_vault",
    "analyze_document": "document_vault",
    "expiry_alerts": "document_vault",
    "delete_document": "document_vault",
    # HR
    "hr_action": "hr_office",
    "add_staff": "hr_office",
    "list_staff": "hr_office",
    "attendance_checkin": "hr_office",
    "attendance_checkout": "hr_office",
    "list_attendance": "hr_office",
    "staff_panel": "hr_office",
    # Self-dev
    "self_update": "self_dev",
    "propose_update": "self_dev",
    "run_safe_test": "self_dev",
    "approve_deploy": "self_dev",
    "list_updates": "self_dev",
    "rollback_update": "self_dev",
    # Graphics
    "design_document": "graphics",
    "list_designs": "graphics",
    "render_template": "graphics",
    "list_templates": "graphics",
    # Social
    "post_social": "social",
    "schedule_post": "social",
    "list_posts": "social",
    "publish_due": "social",
}

# Intents that create side effects and typically need approval gating at brain level
SIDE_EFFECT_INTENTS = {
    "send_email",
    "send_whatsapp",
    "send_wechat",
    "send_sms",
    "call_contact",
    "book_shipment",
    "pay_invoice",
    "mark_paid",
    "file_compliance",
    "delete_document",
    "add_staff",
    "hire",
    "self_update",
    "propose_update",
    "approve_deploy",
    "post_social",
    "schedule_post",
    "publish_due",
}


class CentralBrain:
    """Routes intents to agents, enforces approval matrix, queues OTP-backed approvals."""

    async def status(self) -> dict[str, Any]:
        return {
            "brain": "online",
            "mode": "orchestrator",
            "agents": list_agents(),
            "routes": INTENT_ROUTES,
            "side_effect_intents": sorted(SIDE_EFFECT_INTENTS),
        }

    async def route_intent(
        self,
        db: AsyncSession,
        *,
        intent: str,
        payload: Optional[dict[str, Any]] = None,
        actor_user_id: Optional[UUID] = None,
        actor_username: Optional[str] = None,
        preferred_agent: Optional[str] = None,
        force_execute: bool = False,
    ) -> dict[str, Any]:
        payload = payload or {}
        agent_id = preferred_agent or INTENT_ROUTES.get(intent)
        if not agent_id:
            await write_audit(
                db,
                action="brain.route.unknown",
                actor_user_id=actor_user_id,
                actor_username=actor_username,
                status="failed",
                details={"intent": intent},
                message=f"No route for intent: {intent}",
            )
            return {
                "success": False,
                "message": f"No agent route for intent '{intent}'",
                "intent": intent,
                "hint": "Use /api/v1/brain/status for known intents",
            }

        agent = get_agent(agent_id)
        if not agent:
            return {"success": False, "message": f"Agent '{agent_id}' not registered"}

        approval = await self._check_approval(db, intent=intent, agent_id=agent_id)
        context = {
            "db": db,
            "actor_user_id": str(actor_user_id) if actor_user_id else None,
            "actor_username": actor_username,
            "approval": approval,
            "force_execute": force_execute,
        }

        if approval.get("mode") == "deny":
            await write_audit(
                db,
                action="brain.route.denied",
                actor_user_id=actor_user_id,
                actor_username=actor_username,
                resource_type="agent",
                resource_id=agent_id,
                status="denied",
                details={"intent": intent, "approval": approval},
            )
            return {
                "success": False,
                "message": "Action denied by approval matrix",
                "approval": approval,
            }

        needs_gate = (
            not force_execute
            and approval.get("mode") == "approval"
            and intent in SIDE_EFFECT_INTENTS
        )

        if needs_gate:
            pending = await create_pending_approval(
                db,
                action_key=approval.get("action_key") or intent,
                agent_id=agent_id,
                intent=intent,
                payload=payload,
                requested_by=actor_user_id,
                send_otp=True,
                otp_channel=payload.get("otp_channel", "whatsapp"),
                force_otp_dry_run=bool(payload.get("otp_dry_run")),
            )
            await write_audit(
                db,
                action="brain.approval.queued",
                actor_user_id=actor_user_id,
                actor_username=actor_username,
                resource_type="pending_approval",
                resource_id=pending["approval_id"],
                details={"intent": intent, "agent_id": agent_id},
                message="Queued for owner OTP approval",
            )
            return {
                "success": True,
                "message": "Action queued for owner approval (OTP sent/dry-run)",
                "requires_approval": True,
                "action_key": approval.get("action_key") or intent,
                "pending_approval": pending,
                "agent": agent.info(),
                "approval": approval,
                "executed": False,
            }

        result = await agent.handle(intent, payload, context)

        if approval.get("mode") == "approval":
            result.requires_approval = result.requires_approval or True
            result.action_key = approval.get("action_key") or result.action_key

        await write_audit(
            db,
            action="brain.route",
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            resource_type="agent",
            resource_id=agent_id,
            status="success" if result.success else "failed",
            details={
                "intent": intent,
                "requires_approval": result.requires_approval,
                "agent_status": agent.status,
                "executed": True,
            },
            message=result.message,
        )

        logger.info(
            "brain_routed",
            intent=intent,
            agent_id=agent_id,
            requires_approval=result.requires_approval,
            success=result.success,
        )

        return {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "requires_approval": result.requires_approval,
            "action_key": result.action_key,
            "pending_approval_id": result.pending_approval_id,
            "agent": agent.info(),
            "approval": approval,
            "executed": True,
        }

    async def _check_approval(
        self, db: AsyncSession, *, intent: str, agent_id: str
    ) -> dict[str, Any]:
        keys = [intent, f"{agent_id}.{intent}"]
        for key in keys:
            result = await db.execute(select(ApprovalRule).where(ApprovalRule.action_key == key))
            rule = result.scalar_one_or_none()
            if rule and rule.is_active:
                return {
                    "action_key": rule.action_key,
                    "mode": rule.mode,
                    "amount_limit": float(rule.amount_limit) if rule.amount_limit is not None else None,
                    "requires_owner": rule.requires_owner,
                }
        # Read-only / list intents default to auto
        if intent.startswith("list_") or intent in {
            "find_leads",
            "find_supplier",
            "get_rate",
            "compare_rates",
            "finance_summary",
            "retrieve_document",
            "expiry_alerts",
            "staff_panel",
            "list_templates",
            "seed_rules",
            "run_safe_test",
            "request_owner_otp",
            "verify_owner_otp",
        }:
            return {
                "action_key": intent,
                "mode": "auto",
                "amount_limit": None,
                "requires_owner": False,
            }
        return {
            "action_key": intent,
            "mode": "approval" if intent in SIDE_EFFECT_INTENTS else "auto",
            "amount_limit": None,
            "requires_owner": intent in SIDE_EFFECT_INTENTS,
        }


brain = CentralBrain()
