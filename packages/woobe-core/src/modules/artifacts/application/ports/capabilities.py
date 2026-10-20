"""Version 1 capability ports. Hosts inject adapters through composition."""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Protocol

from modules.artifacts.application.contracts.processing import ProcessingRecipe
from modules.artifacts.domain.models import (
    Action, Artifact, ArtifactRef, CanonicalDocument, DocumentAsset, DocumentIndex, Page,
    ProcessingJob, ProcessingProfile, Revision, Scope, Workspace,
)
from shared.security.principal import SecurityPrincipal
from shared.contracts.object_storage import ObjectMetadata as ObjectMetadata, ObjectStorage as ObjectStorage


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
                      profile: ProcessingRecipe, *,
                      publish_asset: Callable[[DocumentAsset, AsyncIterator[bytes]], Awaitable[None]] | None = None) -> CanonicalDocument: ...


class DocumentModelGateway(Protocol):
    async def summarize(self, *, text: str, max_output_tokens: int,
                        operation_id: str) -> str: ...


class DocumentIndexer(Protocol):
    name: str
    version: str

    async def index(self, document: CanonicalDocument, *, representation_set_id: str,
                    profile: ProcessingRecipe,
                    model: DocumentModelGateway | None = None) -> DocumentIndex: ...


class ProcessingScheduler(Protocol):
    async def schedule(self, scope: Scope, workspace_id: str, reference: ArtifactRef,
                       profile: ProcessingProfile, operation_id: str) -> ProcessingJob: ...


class ArtifactTransferPort(Protocol):
    async def send(self, scope: Scope, workspace_id: str, reference: ArtifactRef,
                   *, tool_id: str, operation_id: str) -> str: ...
