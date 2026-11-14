"""Central AI Brain API."""

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agents.brain import brain
from app.agents.registry import list_agents
from app.api.deps import CurrentUser, DbSession

router = APIRouter(prefix="/brain", tags=["central-brain"])


class RouteRequest(BaseModel):
    intent: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    preferred_agent: Optional[str] = None


@router.get("/status")
async def brain_status(user: CurrentUser):
    return await brain.status()


@router.get("/agents")
async def agents(user: CurrentUser):
    return {"agents": list_agents()}


@router.post("/route")
async def route(body: RouteRequest, db: DbSession, user: CurrentUser):
    return await brain.route_intent(
        db,
        intent=body.intent,
        payload=body.payload,
        actor_user_id=user.id,
        actor_username=user.username,
        preferred_agent=body.preferred_agent,
    )
