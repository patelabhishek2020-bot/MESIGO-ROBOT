"""Stub implementations for agents 2–12 (full logic comes later)."""

from typing import Any

from app.agents.base import AgentResult, BaseAgent


class StubAgent(BaseAgent):
    def __init__(self, agent_id: str, name: str, description: str):
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.status = "stub"

    async def handle(self, intent: str, payload: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        return AgentResult(
            success=True,
            message=f"{self.name} stub received intent '{intent}' — implementation pending",
            data={"intent": intent, "payload": payload, "agent_id": self.agent_id},
            requires_approval=True,
            action_key=f"{self.agent_id}.{intent}",
        )


AGENT_STUB_SPECS = [
    ("lead_crm", "Lead Generation & CRM", "Find, qualify, and manage leads/contacts"),
    ("communication", "Communication", "Email, WhatsApp, WeChat, Phone outreach"),
    ("supplier_rate", "Supplier & Rate", "Source suppliers and negotiate rates"),
    ("logistics", "Logistics & Documentation", "Shipments, B/L, packing, CHA coordination"),
    ("finance", "Finance & Accounting", "Invoices, payments, FX, books"),
    ("compliance", "Compliance & Government Rules", "Licenses, customs, regulatory rules"),
    ("document_vault", "Document Vault", "Secure storage and retrieval of trade docs"),
    ("hr_office", "HR & Office + Staff Panel", "Staff roles, attendance, office ops"),
    ("self_dev", "Self-Development", "Safe self-update with approval and test deploy"),
    ("graphics", "Graphics & Document Design", "Branded docs, labels, visual assets"),
    ("social", "Social Media Management", "Scheduled and approved social posting"),
]


def build_stub_agents() -> dict[str, StubAgent]:
    return {
        agent_id: StubAgent(agent_id, name, description)
        for agent_id, name, description in AGENT_STUB_SPECS
    }
