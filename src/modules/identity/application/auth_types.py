from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    email: str
    status: str


@dataclass(frozen=True)
class AuthenticatedOrganization:
    id: UUID
    name: str
    slug: str
    status: str


@dataclass(frozen=True)
class IssuedAuthentication:
    access_token: str
    refresh_token: str
    session_id: UUID
    token_type: str
    expires_in: int
    user: AuthenticatedUser
    organization: AuthenticatedOrganization | None = None
