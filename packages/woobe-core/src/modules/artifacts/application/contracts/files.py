from dataclasses import dataclass

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


@dataclass(frozen=True)
class ListFiles(FileRequest):
    directory: str = ''
    limit: int = 50
    cursor: str | None = None


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


@dataclass(frozen=True)
class FileSnapshot:
    artifact: Artifact
    revision: Revision | None
    storage_profile: str


@dataclass(frozen=True)
class CopyFile(ReadFile):
    operation_id: str = ''
    destination_path: str = ''
