from dataclasses import dataclass, field
from datetime import datetime

from modules.artifacts.domain.models import Artifact, Revision, Scope
from shared.security.principal import SecurityPrincipal


@dataclass(frozen=True)
class FileRequest:
    principal: SecurityPrincipal
    scope: Scope
    workspace_id: str


@dataclass(frozen=True)
class ReadFile(FileRequest):
    artifact_id: str
    revision_id: str | None = None
    # Internal runtime overlay: a Run may read an exact revision it created.
    # HTTP transports never populate these fields.
    run_id: str | None = field(default=None, kw_only=True)
    output_node_ids: frozenset[str] = field(default_factory=frozenset, kw_only=True)
    catalog_version: int | None = field(default=None, kw_only=True)


@dataclass(frozen=True)
class ListFiles(FileRequest):
    directory: str = ''
    limit: int = 50
    cursor: str | None = None
    catalog_version: int | None = None


@dataclass(frozen=True)
class ListRevisions(FileRequest):
    artifact_id: str = ''
    limit: int = 50
    cursor: str | None = None


@dataclass(frozen=True)
class RevisionHistoryEntry:
    revision: Revision
    created_at: datetime


@dataclass(frozen=True)
class MutateFile(FileRequest):
    operation_id: str
    kind: str
    artifact_id: str | None = None
    expected_version: int | None = None
    path: str | None = None


@dataclass(frozen=True)
class WriteText(FileRequest):
    operation_id: str
    path: str
    text: str
    artifact_id: str | None = None
    expected_revision: str | None = None
    origin: str = 'application'
    run_id: str | None = None
    node_id: str | None = None
    producer_id: str | None = None


@dataclass(frozen=True)
class WriteBytes(FileRequest):
    operation_id: str
    path: str
    content: bytes
    content_type: str
    producer_id: str
    external_operation_ref: str | None = None
    source_refs: tuple[dict, ...] = ()
    run_id: str | None = None
    node_id: str | None = None


@dataclass(frozen=True)
class FileSnapshot:
    artifact: Artifact
    revision: Revision | None
    storage_profile: str


@dataclass(frozen=True)
class CopyFile(ReadFile):
    operation_id: str = ''
    destination_path: str = ''
