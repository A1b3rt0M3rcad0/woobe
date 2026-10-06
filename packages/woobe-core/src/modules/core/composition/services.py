"""Core service factories exposed to process hosts."""

from modules.core.infra.services.control_key_service import ControlKeyService
from modules.core.infra.services.project_access_service import ProjectAccessService
from shared.composition_resources import SESSION_FACTORY
from shared.security.authority import CategoryResolver


def build_project_access_service() -> ProjectAccessService:
    return ProjectAccessService(SESSION_FACTORY)


def build_control_key_service(*, category_resolver: CategoryResolver | None = None) -> ControlKeyService:
    return ControlKeyService(SESSION_FACTORY, category_resolver)


__all__ = ["build_control_key_service", "build_project_access_service"]
