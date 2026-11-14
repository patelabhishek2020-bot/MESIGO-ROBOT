"""Direct agent inventory + convenience invoke (still goes through Brain)."""

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agents.brain import brain
from app.agents.registry import get_agent, list_agents
from app.api.deps import CurrentUser, DbSession
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/agents", tags=["agents"])


class InvokeBody(BaseModel):
    intent: str
    payload: dict[str, Any] = Field(default_factory=dict)
    force_execute: bool = False


@router.get("")
async def agents(user: CurrentUser):
    return {"agents": list_agents()}


@router.get("/{agent_id}")
async def agent_detail(agent_id: str, user: CurrentUser):
    agent = get_agent(agent_id)
    if not agent:
        raise NotFoundError(f"Agent '{agent_id}' not found")
    return agent.info()


@router.post("/{agent_id}/invoke")
async def invoke(agent_id: str, body: InvokeBody, db: DbSession, user: CurrentUser):
    agent = get_agent(agent_id)
    if not agent:
        raise NotFoundError(f"Agent '{agent_id}' not found")
    return await brain.route_intent(
        db,
        intent=body.intent,
        payload=body.payload,
        actor_user_id=user.id,
        actor_username=user.username,
        preferred_agent=agent_id,
        force_execute=body.force_execute,
    )
