"""Legacy stub factory — retained for reference; registry now uses real agents."""

from app.agents.registry import AGENT_REGISTRY, list_agents


def build_stub_agents():
    """Deprecated: real agents are registered in app.agents.registry."""
    return dict(AGENT_REGISTRY)


__all__ = ["build_stub_agents", "list_agents"]
