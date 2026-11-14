"""Central agent registry."""

from typing import Optional

from app.agents.base import BaseAgent
from app.agents.stubs import build_stub_agents

AGENT_REGISTRY: dict[str, BaseAgent] = build_stub_agents()


def get_agent(agent_id: str) -> Optional[BaseAgent]:
    return AGENT_REGISTRY.get(agent_id)


def list_agents() -> list[dict]:
    return [agent.info() for agent in AGENT_REGISTRY.values()]


def register_agent(agent: BaseAgent) -> None:
    AGENT_REGISTRY[agent.agent_id] = agent
