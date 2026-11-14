"""Base agent interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AgentResult:
    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False
    action_key: Optional[str] = None


class BaseAgent(ABC):
    agent_id: str
    name: str
    description: str
    status: str = "stub"  # stub|ready|disabled

    @abstractmethod
    async def handle(self, intent: str, payload: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        ...

    def info(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
        }
