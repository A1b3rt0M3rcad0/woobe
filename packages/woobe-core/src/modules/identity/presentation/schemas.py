from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateUserRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    status: str
    created_at: datetime


class CreateWorkspaceRequest(BaseModel):
    name: str
    slug: str


class UpdateWorkspaceRequest(BaseModel):
    name: str | None = None
    slug: str | None = None


class WorkspaceResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    created_at: datetime | None = None


class AddMemberRequest(BaseModel):
    user_id: UUID
    role: str


class MemberResponse(BaseModel):
    id: UUID
    user_id: UUID
    workspace_id: UUID
    role: str
    status: str


class InviteRequest(BaseModel):
    email: str
    role: str = "member"


class InviteResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    email: str
    role: str
    status: str
    expires_at: datetime | None = None
    created_at: datetime | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: dict


class RegisterRequest(BaseModel):
    email: str
    password: str
