from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

import uuid6

from modules.identity.domain.enums import (
    InviteStatus,
    MemberRole,
    MemberStatus,
    WorkspaceStatus,
    UserSessionStatus,
    UserStatus,
)


@dataclass
class User:
    id: UUID = field(default_factory=uuid6.uuid7)
    email: str = ""
    password: bytes = b""
    status: UserStatus = UserStatus.active
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Workspace:
    id: UUID = field(default_factory=uuid6.uuid7)
    name: str = ""
    slug: str = ""
    status: WorkspaceStatus = WorkspaceStatus.active
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class WorkspaceMember:
    id: UUID = field(default_factory=uuid6.uuid7)
    user_id: UUID = field(default_factory=uuid6.uuid7)
    workspace_id: UUID = field(default_factory=uuid6.uuid7)
    role: MemberRole = MemberRole.member
    status: MemberStatus = MemberStatus.active
    joined_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class WorkspaceInvite:
    id: UUID = field(default_factory=uuid6.uuid7)
    workspace_id: UUID = field(default_factory=uuid6.uuid7)
    email: str = ""
    role: MemberRole = MemberRole.member
    token_hash: str = ""
    invited_by_user_id: UUID = field(default_factory=uuid6.uuid7)
    status: InviteStatus = InviteStatus.pending
    expires_at: datetime | None = None
    accepted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class UserSession:
    id: UUID = field(default_factory=uuid6.uuid7)
    user_id: UUID = field(default_factory=uuid6.uuid7)
    refresh_token_hash: bytes = b""
    user_agent: str | None = None
    ip_address: str | None = None
    status: UserSessionStatus = UserSessionStatus.active
    revoked_at: datetime | None = None
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
