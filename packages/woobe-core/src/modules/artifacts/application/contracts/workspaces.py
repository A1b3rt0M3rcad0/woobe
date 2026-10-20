from dataclasses import dataclass
from datetime import datetime

from modules.artifacts.application.contracts.api import WorkspaceCreate, WorkspaceUpdate
from modules.artifacts.domain.models import Action, Scope
from shared.security.principal import SecurityPrincipal


@dataclass(frozen=True)
class CreateWorkspace:
    principal: SecurityPrincipal
    scope: Scope
    definition: WorkspaceCreate


@dataclass(frozen=True)
class ReadWorkspace:
    principal: SecurityPrincipal
    scope: Scope
    workspace_id: str


@dataclass(frozen=True)
class ResolveWorkspace:
    principal: SecurityPrincipal
    scope: Scope
    external_namespace: str
    external_key: str


@dataclass(frozen=True)
class ListWorkspaces:
    principal: SecurityPrincipal
    scope: Scope
    limit: int = 50
    cursor: str | None = None
    external_namespace: str | None = None


@dataclass(frozen=True)
class ChangeWorkspace:
    principal: SecurityPrincipal
    scope: Scope
    workspace_id: str
    definition: WorkspaceUpdate


@dataclass(frozen=True)
class CreateWorkspaceGrant:
    principal: SecurityPrincipal
    scope: Scope
    subject_id: str
    actions: frozenset[Action]
    workspace_id: str | None = None
    external_namespace: str | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True)
class RevokeWorkspaceGrant:
    principal: SecurityPrincipal
    scope: Scope
    grant_id: str
