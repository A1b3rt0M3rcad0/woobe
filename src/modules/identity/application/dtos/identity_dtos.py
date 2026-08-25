from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from modules.identity.domain.enums import (
    InviteStatus,
    MemberRole,
    MemberStatus,
    WorkspaceStatus,
    UserStatus,
)


class CreateUserInput(BaseModel):
    email: str
    password: str


class CreateUserOutput(BaseModel):
    id: UUID
    email: str
    status: UserStatus
    created_at: datetime


class CreateWorkspaceInput(BaseModel):
    name: str
    slug: str


class CreateWorkspaceOutput(BaseModel):
    id: UUID
    name: str
    slug: str
    status: WorkspaceStatus
    created_at: datetime


class UpdateWorkspaceInput(BaseModel):
    name: str | None = None
    slug: str | None = None


class UpdateWorkspaceOutput(BaseModel):
    id: UUID
    name: str
    slug: str
    status: WorkspaceStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AddMemberInput(BaseModel):
    user_id: UUID
    workspace_id: UUID
    role: MemberRole = MemberRole.member


class AddMemberOutput(BaseModel):
    id: UUID
    user_id: UUID
    workspace_id: UUID
    role: MemberRole
    status: MemberStatus
    joined_at: datetime


class InviteUserInput(BaseModel):
    workspace_id: UUID
    email: str
    role: MemberRole = MemberRole.member
    invited_by_user_id: UUID


class InviteUserOutput(BaseModel):
    id: UUID
    workspace_id: UUID
    email: str
    role: MemberRole
    status: InviteStatus
    expires_at: datetime
    created_at: datetime


class ListWorkspacesInput(BaseModel):
    pass


class ListWorkspacesOutput(BaseModel):
    id: UUID
    name: str
    slug: str
    status: WorkspaceStatus
    created_at: datetime | None = None


class LoginInput(BaseModel):
    email: str
    password: str


class LoginOutput(BaseModel):
    token: str
    user: dict


class RegisterInput(BaseModel):
    email: str
    password: str
    workspace_name: str = "My Workspace"


class RegisterOutput(BaseModel):
    token: str
    user: dict
    workspace: dict | None = None


class GetWorkspaceInput(BaseModel):
    workspace_id: UUID


class GetWorkspaceOutput(BaseModel):
    id: UUID
    name: str
    slug: str
    status: WorkspaceStatus
    created_at: datetime | None = None


class ListMembersInput(BaseModel):
    workspace_id: UUID


class ListMembersOutput(BaseModel):
    id: UUID
    user_id: UUID
    workspace_id: UUID
    role: MemberRole
    status: MemberStatus
    joined_at: datetime | None = None


class ListInvitesInput(BaseModel):
    workspace_id: UUID


class ListInvitesOutput(BaseModel):
    id: UUID
    workspace_id: UUID
    email: str
    role: MemberRole
    status: InviteStatus
    expires_at: datetime | None = None
    created_at: datetime | None = None


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
