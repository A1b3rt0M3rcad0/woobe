from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from modules.identity.domain.enums import InviteStatus, UserStatus


class CreateUserInput(BaseModel):
    email: str
    password: str


class CreateUserOutput(BaseModel):
    id: UUID
    email: str
    status: UserStatus
    created_at: datetime


class LoginInput(BaseModel):
    email: str
    password: str


class LoginOutput(BaseModel):
    token: str
    user: dict


class RegisterInput(BaseModel):
    email: str
    password: str


class RegisterOutput(BaseModel):
    token: str
    user: dict


class GetUserInput(BaseModel):
    user_id: UUID


class GetUserOutput(BaseModel):
    id: UUID
    email: str
    status: UserStatus
    created_at: datetime | None = None


class GetCurrentUserInput(BaseModel):
    pass


class GetCurrentUserOutput(BaseModel):
    email: str
    name: str | None = None


class InviteUserInput(BaseModel):
    workspace_id: UUID
    email: str
    project_ids: list[UUID] = []


class InviteUserOutput(BaseModel):
    id: UUID
    workspace_id: UUID
    email: str
    status: InviteStatus
    expires_at: datetime
    created_at: datetime | None = None
