"""Central AI Brain — Master Orchestrator (foundation)."""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.registry import get_agent, list_agents
from app.core.logging import get_logger
from app.models.settings import ApprovalRule
from app.services.audit import write_audit
from sqlalchemy import select

logger = get_logger("brain")

# Rough intent → agent routing map (LLM will refine later)
INTENT_ROUTES: dict[str, str] = {
    "find_leads": "lead_crm",
    "manage_crm": "lead_crm",
    "send_email": "communication",
    "send_whatsapp": "communication",
    "call_contact": "communication",
    "find_supplier": "supplier_rate",
    "get_rate": "supplier_rate",
    "book_shipment": "logistics",
    "prepare_docs": "logistics",
    "pay_invoice": "finance",
    "create_invoice": "finance",
    "check_compliance": "compliance",
    "store_document": "document_vault",
    "retrieve_document": "document_vault",
    "hr_action": "hr_office",
    "self_update": "self_dev",
    "design_document": "graphics",
    "post_social": "social",
}


class CentralBrain:
    """Routes intents to agents, enforces approval matrix stubs."""

    async def status(self) -> dict[str, Any]:
        return {
            "brain": "online",
            "mode": "orchestrator",
            "agents": list_agents(),
            "routes": INTENT_ROUTES,
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
    ) -> dict[str, Any]:
        payload = payload or {}
        agent_id = preferred_agent or INTENT_ROUTES.get(intent)
        if not agent_id:
            # Fallback: ask communication/lead stubs later; for now return unknown
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
            }

        agent = get_agent(agent_id)
        if not agent:
            return {"success": False, "message": f"Agent '{agent_id}' not registered"}

        approval = await self._check_approval(db, intent=intent, agent_id=agent_id)
        context = {
            "actor_user_id": str(actor_user_id) if actor_user_id else None,
            "actor_username": actor_username,
            "approval": approval,
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

        result = await agent.handle(intent, payload, context)

        # If matrix requires approval, mark and do not execute side effects (stubs anyway)
        if approval.get("mode") == "approval":
            result.requires_approval = True
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
            },
            message=result.message,
        )

        logger.info(
            "brain_routed",
            intent=intent,
            agent_id=agent_id,
            requires_approval=result.requires_approval,
        )

        return {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "requires_approval": result.requires_approval,
            "action_key": result.action_key,
            "agent": agent.info(),
            "approval": approval,
        }

    async def _check_approval(
        self, db: AsyncSession, *, intent: str, agent_id: str
    ) -> dict[str, Any]:
        # Try exact intent as action_key, then agent_id.intent
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
        # Default: require approval for stub actions
        return {
            "action_key": intent,
            "mode": "approval",
            "amount_limit": None,
            "requires_owner": True,
        }


brain = CentralBrain()
