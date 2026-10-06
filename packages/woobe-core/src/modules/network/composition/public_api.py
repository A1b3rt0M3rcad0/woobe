"""Explicit public surface consumed by process hosts.

The API and worker packages import Network capabilities through ``entrypoint``.
Concrete persistence types remain assembled inside this outer composition layer,
which prevents hosts from reaching through the bounded-context package graph.
"""

from modules.network.composition.portable_export import build_portable_network_export_reader

from modules.network.infra.services.boundary_service import NetworkBoundaryService
from modules.network.composition.imported_network import imported_network_composer
from modules.network.composition.services import (
    build_network_rerun_service,
    build_network_service,
)
from modules.network.domain.enums import NetworkEnvironment
from modules.network.presentation.schemas import (
    CreateNetworkSessionRequest,
    EnsureNetworkRequest,
    PromotionRequest,
    RollbackNetworkRequest,
    RunNetworkRequest,
    SaveNetworkDraftRequest,
)

__all__ = [
    "imported_network_composer",
    "CreateNetworkSessionRequest",
    "EnsureNetworkRequest",
    "NetworkBoundaryService",
    "NetworkEnvironment",
    "PromotionRequest",
    "RollbackNetworkRequest",
    "RunNetworkRequest",
    "SaveNetworkDraftRequest",
    "build_network_rerun_service",
    "build_network_service",
]

__all__.append("build_portable_network_export_reader")
