from dataclasses import dataclass
from datetime import datetime

from modules.artifacts.application.contracts.api import UploadCreate
from modules.artifacts.domain.models import ArtifactRef, Scope, UploadStatus
from shared.security.principal import SecurityPrincipal


@dataclass(frozen=True)
class BeginUpload:
    principal: SecurityPrincipal
    scope: Scope
    workspace_id: str
    definition: UploadCreate


@dataclass(frozen=True)
class UploadRequest:
    principal: SecurityPrincipal
    scope: Scope
    workspace_id: str
    upload_id: str


@dataclass(frozen=True)
class UploadPart(UploadRequest):
    offset: int
    content: bytes


@dataclass(frozen=True)
class UploadView:
    id: str
    operation_id: str
    workspace_id: str
    offset: int
    expected_size: int
    status: UploadStatus
    expires_at: datetime
    receipt: ArtifactRef | None = None


@dataclass(frozen=True)
class UploadSnapshot:
    view: UploadView
    artifact_id: str
    revision_id: str
    path: str
    sha256: str
    content_type: str
    storage_profile: str
    object_key: str
    parts: tuple[dict, ...]
    expected_revision: str | None


@dataclass(frozen=True)
class RecordPart(UploadRequest):
    offset: int
    key: str
    size: int
    sha256: str


@dataclass(frozen=True)
class CommitUpload(UploadRequest):
    size: int
    sha256: str
    content_type: str
    version_id: str | None = None
