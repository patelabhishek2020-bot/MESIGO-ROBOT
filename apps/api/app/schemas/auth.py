"""Auth schemas."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    must_change_password: bool = False
    setup_required: bool = False


class UserOut(BaseModel):
    id: UUID
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    is_owner: bool
    must_change_password: bool
    roles: list[str] = []

    model_config = {"from_attributes": True}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class VoiceEnrollRequest(BaseModel):
    label: str = "primary"
    enrollment_phrase: str = Field(
        default="Mesigo AI authorize my voice for business operations",
        max_length=255,
    )


class VoiceEnrollResponse(BaseModel):
    id: UUID
    status: str
    label: str
    enrollment_phrase: str
    sample_path: Optional[str] = None
    message: str
