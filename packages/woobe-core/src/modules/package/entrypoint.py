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
