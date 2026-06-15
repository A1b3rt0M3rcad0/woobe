from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from modules.identity.domain.enums import (
    InviteStatus,
    MemberRole,
    MemberStatus,
    OrganizationStatus,
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


class CreateOrganizationInput(BaseModel):
    name: str
    slug: str


class CreateOrganizationOutput(BaseModel):
    id: UUID
    name: str
    slug: str
    status: OrganizationStatus
    created_at: datetime


class UpdateOrganizationInput(BaseModel):
    name: str | None = None
    slug: str | None = None


class UpdateOrganizationOutput(BaseModel):
    id: UUID
    name: str
    slug: str
    status: OrganizationStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AddMemberInput(BaseModel):
    user_id: UUID
    organization_id: UUID
    role: MemberRole = MemberRole.member


class AddMemberOutput(BaseModel):
    id: UUID
    user_id: UUID
    organization_id: UUID
    role: MemberRole
    status: MemberStatus
    joined_at: datetime


class InviteUserInput(BaseModel):
    organization_id: UUID
    email: str
    role: MemberRole = MemberRole.member
    invited_by_user_id: UUID


class InviteUserOutput(BaseModel):
    id: UUID
    organization_id: UUID
    email: str
    role: MemberRole
    status: InviteStatus
    expires_at: datetime
    created_at: datetime


class ListOrganizationsInput(BaseModel):
    pass


class ListOrganizationsOutput(BaseModel):
    id: UUID
    name: str
    slug: str
    status: OrganizationStatus
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
    organization_name: str


class RegisterOutput(BaseModel):
    token: str
    user: dict


class GetOrganizationInput(BaseModel):
    organization_id: UUID


class GetOrganizationOutput(BaseModel):
    id: UUID
    name: str
    slug: str
    status: OrganizationStatus
    created_at: datetime | None = None


class ListMembersInput(BaseModel):
    organization_id: UUID


class ListMembersOutput(BaseModel):
    id: UUID
    user_id: UUID
    organization_id: UUID
    role: MemberRole
    status: MemberStatus
    joined_at: datetime | None = None


class ListInvitesInput(BaseModel):
    organization_id: UUID


class ListInvitesOutput(BaseModel):
    id: UUID
    organization_id: UUID
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
