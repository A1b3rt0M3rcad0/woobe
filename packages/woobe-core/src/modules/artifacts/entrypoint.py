"""Host-facing capability boundary for Artifacts."""

from modules.artifacts.composition.public_api import (
    CONTRACT_VERSION as CONTRACT_VERSION,
    ArtifactError as ArtifactError,
    ArtifactReference as ArtifactReference,
    CapabilityDescriptor as CapabilityDescriptor,
    ErrorEnvelope as ErrorEnvelope,
    SourceReference as SourceReference,
    UploadCreate as UploadCreate,
    WorkspaceCreate as WorkspaceCreate,
    WorkspaceUpdate as WorkspaceUpdate,
)
