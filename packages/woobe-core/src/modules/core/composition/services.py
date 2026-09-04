"""Core service factories exposed to process hosts."""

from modules.core.infra.services.project_access_service import ProjectAccessService
from shared.composition_resources import SESSION_FACTORY


def build_project_access_service() -> ProjectAccessService:
    return ProjectAccessService(SESSION_FACTORY)


__all__ = ["build_project_access_service"]
