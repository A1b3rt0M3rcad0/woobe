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


class ControlPlanePrincipal(BaseModel):
    model_config = ConfigDict(frozen=True)

    api_key_id: UUID
    credential_id: UUID
    workspace_id: UUID
    key_prefix: str
    permissions: frozenset[str] = Field(default_factory=frozenset)
    kind: str = "control"
    authenticated_at: datetime
    expires_at: datetime | None = None
    delegation_expires_at: datetime | None = None
    on_project_create_permissions: frozenset[str] = Field(default_factory=frozenset)

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions


class ProjectApiPrincipal(BaseModel):
    model_config = ConfigDict(frozen=True)

    api_key_id: UUID
    project_id: UUID
    key_prefix: str
    scopes: frozenset[str] = Field(default_factory=frozenset)
    kind: str = "project"
    agent_id: UUID | None = None
    target_type: str | None = None
    target_id: UUID | None = None
    environment: str | None = None
    interfaces: frozenset[str] = Field(default_factory=frozenset)
    authenticated_at: datetime

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    def allows_interface(self, interface: str) -> bool:
        return interface in self.interfaces


SecurityPrincipal: TypeAlias = (
    AuthenticatedPrincipal | ProjectApiPrincipal | ControlPlanePrincipal
)
