from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    email: str
    status: str


@dataclass(frozen=True)
class IssuedAuthentication:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: AuthenticatedUser
