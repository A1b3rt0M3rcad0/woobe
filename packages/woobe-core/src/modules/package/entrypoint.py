"""Stable public Package API for process hosts."""

from modules.package.composition.public_api import (
    ExportPackageRequest,
    PlanPackageRequest,
    ApplyPackageRequest,
    LookupPackageOperationRequest,
    ResumePackageOperationRequest,
    PackageError,
    build_package_service,
)

__all__ = [
    "ExportPackageRequest",
    "PlanPackageRequest",
    "ApplyPackageRequest",
    "LookupPackageOperationRequest",
    "ResumePackageOperationRequest",
    "PackageError",
    "build_package_service",
]

# Closed object retention gateway; Agent/Network own their lifecycle records.
from modules.package.composition.snapshot_artifacts import build_snapshot_artifacts
from modules.package.composition.candidate_preparation import build_candidate_preparation

from modules.package.composition.public_api import assert_package_configuration_quiescent
__all__.append("assert_package_configuration_quiescent")

from modules.package.composition.public_api import configure_package_configuration_barrier
__all__.append("configure_package_configuration_barrier")
