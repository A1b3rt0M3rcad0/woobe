from dataclasses import dataclass
from uuid import UUID

from modules.identity.domain.entities import Workspace
from modules.identity.domain.enums import MemberRole


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    email: str
    status: str


@dataclass(frozen=True)
class AuthenticatedWorkspace:
    id: UUID
    name: str
    slug: str
    status: str


@dataclass(frozen=True)
class IssuedSession:
    id: UUID
    user_id: UUID
    secret: str


@dataclass(frozen=True)
class SessionRotation:
    session: IssuedSession | None = None
    error: str | None = None


@dataclass(frozen=True)
class IssuedAuthentication:
    access_token: str
    refresh_token: str
    session_id: UUID
    token_type: str
    expires_in: int
    user: AuthenticatedUser
    workspace: AuthenticatedWorkspace | None = None


@dataclass(frozen=True)
class AuthenticationAttempt:
    authentication: IssuedAuthentication | None = None
    error: str | None = None


@dataclass(frozen=True)
class AcceptedWorkspaceInvite:
    workspace: Workspace
    member_id: UUID
    membership_changed: bool
    role: MemberRole
