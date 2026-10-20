"""Explicit public Artifacts types; concrete wiring is added with capabilities."""

from modules.artifacts.application.contracts.api import (
    ArtifactReference as ArtifactReference,
    CapabilityDescriptor as CapabilityDescriptor,
    ErrorEnvelope as ErrorEnvelope,
    SourceReference as SourceReference,
    UploadCreate as UploadCreate,
    WorkspaceCreate as WorkspaceCreate,
    WorkspaceUpdate as WorkspaceUpdate,
)
from modules.artifacts.domain.models import ArtifactError as ArtifactError


CONTRACT_VERSION = '1'
