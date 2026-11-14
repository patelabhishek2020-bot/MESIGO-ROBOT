"""Central agent registry — real modules for agents 2–12."""

from typing import Optional

from app.agents.base import BaseAgent
from app.agents.communication import CommunicationAgent
from app.agents.compliance import ComplianceAgent
from app.agents.document_vault import DocumentVaultAgent
from app.agents.finance import FinanceAgent
from app.agents.graphics import GraphicsAgent
from app.agents.hr import HrOfficeAgent
from app.agents.lead_crm import LeadCrmAgent
from app.agents.logistics import LogisticsAgent
from app.agents.self_dev import SelfDevAgent
from app.agents.social import SocialAgent
from app.agents.supplier import SupplierRateAgent

AGENT_REGISTRY: dict[str, BaseAgent] = {}


def _build_registry() -> dict[str, BaseAgent]:
    agents: list[BaseAgent] = [
        LeadCrmAgent(),
        CommunicationAgent(),
        SupplierRateAgent(),
        LogisticsAgent(),
        FinanceAgent(),
        ComplianceAgent(),
        DocumentVaultAgent(),
        HrOfficeAgent(),
        SelfDevAgent(),
        GraphicsAgent(),
        SocialAgent(),
    ]
    return {a.agent_id: a for a in agents}


AGENT_REGISTRY.update(_build_registry())


def get_agent(agent_id: str) -> Optional[BaseAgent]:
    return AGENT_REGISTRY.get(agent_id)


def list_agents() -> list[dict]:
    return [agent.info() for agent in AGENT_REGISTRY.values()]


def register_agent(agent: BaseAgent) -> None:
    AGENT_REGISTRY[agent.agent_id] = agent
