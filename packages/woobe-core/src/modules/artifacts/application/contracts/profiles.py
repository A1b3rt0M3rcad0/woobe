from dataclasses import dataclass

from modules.artifacts.application.contracts.processing import ProfileCreate, ProfileDefault
from modules.artifacts.domain.models import Scope
from shared.security.principal import SecurityPrincipal


@dataclass(frozen=True)
class CreateProcessingProfile:
    principal: SecurityPrincipal
    scope: Scope
    definition: ProfileCreate


@dataclass(frozen=True)
class ReadProcessingProfile:
    principal: SecurityPrincipal
    scope: Scope
    profile_id: str
    revision: int


@dataclass(frozen=True)
class ListProcessingProfiles:
    principal: SecurityPrincipal
    scope: Scope
    limit: int = 50
    cursor: str | None = None


@dataclass(frozen=True)
class BindProcessingProfile:
    principal: SecurityPrincipal
    scope: Scope
    workspace_id: str
    definition: ProfileDefault


@dataclass(frozen=True)
class SelectProcessingProfile:
    principal: SecurityPrincipal
    scope: Scope
    workspace_id: str
    profile_id: str | None = None
    profile_revision: int | None = None
