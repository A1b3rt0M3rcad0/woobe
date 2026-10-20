"""Canonical versioned DTOs; no HTTP/framework/provider types."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from modules.artifacts.domain.models import (
    Environment, ErrorCode, ID_PATTERN, Locator, SHA256_PATTERN, SourceRef, logical_path,
)


Identifier = Annotated[str, Field(pattern=f'^{ID_PATTERN}$')]
Digest = Annotated[str, Field(pattern=f'^{SHA256_PATTERN}$')]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class ArtifactReference(Contract):
    artifact_id: Identifier
    revision_id: Identifier


class SourceLocator(Contract):
    block_id: Identifier | None = None
    page_index: int | None = None
    page_number: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    bbox: tuple[float, float, float, float] | None = None

    @model_validator(mode='after')
    def validate_locator(self):
        Locator(**self.model_dump())
        return self


class SourceReference(ArtifactReference):
    source_sha256: Digest
    representation_set_id: Identifier | None = None
    document_index_id: Identifier | None = None
    node_id: Identifier | None = None
    locator: SourceLocator | None = None
    excerpt_sha256: Digest | None = None

    @model_validator(mode='after')
    def validate_source(self):
        values = self.model_dump(exclude={'locator'})
        SourceRef(**values, locator=Locator(**self.locator.model_dump()) if self.locator else None)
        return self


class WorkspaceCreate(Contract):
    schema_version: Literal['1'] = '1'
    environment: Environment
    external_namespace: str = Field(min_length=1, max_length=255)
    external_key: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    storage_profile: Identifier = 'local'
    quota_bytes: int = Field(default=1_073_741_824, ge=0, le=9_223_372_036_854_775_807)
    retention_days: int = Field(default=30, ge=0, le=36500)
    labels: dict[str, str] = Field(default_factory=dict, max_length=32)

    @model_validator(mode='after')
    def validate_names(self):
        for value in (self.external_namespace, self.external_key, self.name):
            if not value.strip() or '\x00' in value:
                raise ValueError('Workspace names and external identities cannot be blank')
        return self


class WorkspaceUpdate(Contract):
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: Literal['active', 'archived', 'deletion_pending'] | None = None
    labels: dict[str, str] | None = Field(default=None, max_length=32)


class UploadCreate(Contract):
    schema_version: Literal['1'] = '1'
    operation_id: Identifier
    path: str = Field(max_length=1024)
    size_bytes: int = Field(ge=0)
    sha256: Digest
    content_type: str = Field(min_length=3, max_length=255,
        pattern=r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+/[!#$%&'*+.^_`|~0-9A-Za-z-]+(?:;[ -~]+)?$")
    artifact_id: Identifier | None = None
    expected_revision: Identifier | None = None

    @model_validator(mode='after')
    def validate_upload(self):
        logical_path(self.path)
        if (not self.content_type.isascii() or '/' not in self.content_type
                or any(ord(character) < 32 or ord(character) == 127 for character in self.content_type)):
            raise ValueError('Invalid declared content type')
        if (self.artifact_id is None) != (self.expected_revision is None):
            raise ValueError('Updating content requires artifact identity and expected revision')
        return self


class ErrorEnvelope(Contract):
    schema_version: Literal['1'] = '1'
    code: ErrorCode
    message: str = Field(max_length=500)
    correlation_id: Identifier
    retryable: bool = False


class CursorEnvelope(Contract):
    schema_version: Literal['1'] = '1'
    scope_fingerprint: Digest
    last_id: Identifier
    catalog_version: int = Field(ge=0)
    purpose: Literal['workspaces', 'artifacts', 'search', 'nodes', 'profiles']


class CapabilityDescriptor(Contract):
    schema_version: Literal['1'] = '1'
    processors: tuple[str, ...] = ()
    indexers: tuple[str, ...] = ()
    media_types: tuple[str, ...] = ()
    transfer_modes: tuple[str, ...] = ()
    max_upload_bytes: int = Field(ge=0)
    max_read_bytes: int = Field(gt=0)
    max_page_size: int = Field(gt=0, le=1000)
    max_upload_part_bytes: int = Field(default=262144, gt=0, le=8388608)
    max_upload_parts: int = Field(default=4096, gt=0, le=4096)
    max_inline_bytes: int = Field(default=262144, gt=0, le=262144)
    max_request_bytes: int = Field(default=262144, gt=0, le=8388608)
    downloads: tuple[str, ...] = ()
    signed_upload_urls: bool = False
    storage_readiness: Literal['not_probed', 'ready', 'unavailable'] = 'not_probed'


class WorkspaceView(WorkspaceCreate):
    default_profile_id: Identifier | None = None
    default_profile_revision: int | None = Field(default=None, ge=1)
    id: Identifier
    project_id: Identifier
    status: Literal['active', 'archived', 'deletion_pending', 'purged']
    version: int = Field(ge=1)
    catalog_version: int = Field(ge=0)
    used_bytes: int = Field(ge=0)
    reserved_bytes: int = Field(ge=0)


class RevisionView(Contract):
    schema_version: Literal['1'] = '1'
    id: Identifier
    artifact_id: Identifier
    content_type: str
    size_bytes: int = Field(ge=0)
    sha256: Digest
    origin: Literal['upload', 'application', 'agent', 'tool', 'processing', 'copy']
    producer_id: Identifier | None = None
    operation_id: Identifier | None = None
    run_id: Identifier | None = None
    node_id: Identifier | None = None


class ArtifactView(Contract):
    schema_version: Literal['1'] = '1'
    id: Identifier
    workspace_id: Identifier
    path: str
    kind: Literal['file', 'directory']
    revision_id: Identifier | None = None
    version: int = Field(ge=1)
    deleted: bool = False
    revision: RevisionView | None = None


class UploadStatusView(Contract):
    schema_version: Literal['1'] = '1'
    id: Identifier
    workspace_id: Identifier
    operation_id: Identifier
    expected_size: int = Field(ge=0)
    offset: int = Field(ge=0)
    status: Literal['created', 'uploading', 'verifying', 'committed', 'failed', 'aborted', 'expired']
    expires_at: AwareDatetime
    receipt: ArtifactReference | None = None


class WorkspacePage(Contract):
    schema_version: Literal['1'] = '1'
    items: tuple[WorkspaceView, ...]
    has_more: bool
    next_cursor: str | None = None
    truncated: bool = False


class ArtifactPage(Contract):
    schema_version: Literal['1'] = '1'
    items: tuple[ArtifactView, ...]
    has_more: bool
    next_cursor: str | None = None
    truncated: bool = False
