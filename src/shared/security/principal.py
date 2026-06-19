from datetime import datetime
from typing import TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuthenticatedPrincipal(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: UUID
    session_id: UUID
    issued_at: datetime
    expires_at: datetime


class ProjectApiPrincipal(BaseModel):
    model_config = ConfigDict(frozen=True)

    api_key_id: UUID
    project_id: UUID
    key_prefix: str
    scopes: frozenset[str] = Field(default_factory=frozenset)
    authenticated_at: datetime

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


SecurityPrincipal: TypeAlias = AuthenticatedPrincipal | ProjectApiPrincipal
