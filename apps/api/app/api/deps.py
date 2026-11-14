"""FastAPI dependencies — auth & DB."""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    authorization: Annotated[Optional[str], Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise UnauthorizedError(str(exc)) from exc

    sub = payload.get("sub")
    if not sub:
        raise UnauthorizedError("Invalid token subject")

    try:
        user_id = UUID(sub)
    except ValueError as exc:
        raise UnauthorizedError("Invalid token subject") from exc

    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise UnauthorizedError("User inactive or not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_owner(user: CurrentUser) -> User:
    if not user.is_owner:
        raise ForbiddenError("Owner access required")
    return user


OwnerUser = Annotated[User, Depends(require_owner)]


def client_meta(request: Request) -> dict[str, Optional[str]]:
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }
