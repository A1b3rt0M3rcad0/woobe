"""Version 1 capability ports. Hosts inject adapters through composition."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from modules.artifacts.domain.models import (
    Action, Artifact, ArtifactRef, CanonicalDocument, DocumentIndex, Page,
    ProcessingJob, ProcessingProfile, Revision, Scope, Workspace,
)
from shared.security.principal import SecurityPrincipal


@dataclass(frozen=True)
class ObjectMetadata:
    key: str
    size_bytes: int
    sha256: str
    content_type: str
    version_id: str | None = None


class ObjectStorage(Protocol):
    contract_version: str

    async def put(self, key: str, chunks: AsyncIterator[bytes], *, size_bytes: int,
                  sha256: str, content_type: str) -> ObjectMetadata: ...

    def open(self, key: str, *, start: int = 0, end: int | None = None
             ) -> AsyncIterator[bytes]: ...

    async def stat(self, key: str) -> ObjectMetadata: ...

    async def delete(self, key: str) -> None: ...


class WorkspaceAuthorizer(Protocol):
    async def authorize(self, principal: SecurityPrincipal, scope: Scope, workspace_id: str,
                        action: Action) -> Workspace: ...


class ArtifactGateway(Protocol):
    async def workspace(self, scope: Scope, workspace_id: str) -> Workspace: ...

    async def list_artifacts(self, scope: Scope, workspace_id: str, *, limit: int,
                             cursor: str | None = None,
                             catalog_version: int | None = None) -> Page[Artifact]: ...

    async def revision(self, scope: Scope, workspace_id: str,
                       reference: ArtifactRef) -> Revision: ...


class DocumentProcessor(Protocol):
    name: str
    version: str
    media_types: frozenset[str]

    async def process(self, revision: Revision, content: AsyncIterator[bytes],
                      profile: ProcessingProfile) -> CanonicalDocument: ...


class DocumentModelGateway(Protocol):
    async def summarize(self, *, text: str, max_output_tokens: int,
                        operation_id: str) -> str: ...


class DocumentIndexer(Protocol):
    name: str
    version: str

    async def index(self, document: CanonicalDocument, *, representation_set_id: str,
                    profile: ProcessingProfile,
                    model: DocumentModelGateway | None = None) -> DocumentIndex: ...


class ProcessingScheduler(Protocol):
    async def schedule(self, scope: Scope, workspace_id: str, reference: ArtifactRef,
                       profile: ProcessingProfile, operation_id: str) -> ProcessingJob: ...


class ArtifactTransferPort(Protocol):
    async def send(self, scope: Scope, workspace_id: str, reference: ArtifactRef,
                   *, tool_id: str, operation_id: str) -> str: ...
