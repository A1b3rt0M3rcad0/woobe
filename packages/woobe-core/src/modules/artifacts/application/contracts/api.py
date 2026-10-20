"""Canonical versioned DTOs; no HTTP/framework/provider types."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    quota_bytes: int = Field(default=1_073_741_824, ge=0)
    retention_days: int = Field(default=30, ge=0, le=36500)

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


class UploadCreate(Contract):
    schema_version: Literal['1'] = '1'
    operation_id: Identifier
    path: str = Field(max_length=1024)
    size_bytes: int = Field(ge=0)
    sha256: Digest
    content_type: str = Field(min_length=3, max_length=255)
    artifact_id: Identifier | None = None
    expected_revision: Identifier | None = None

    @model_validator(mode='after')
    def validate_upload(self):
        logical_path(self.path)
        if '/' not in self.content_type or '\r' in self.content_type or '\n' in self.content_type:
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
    purpose: Literal['workspaces', 'artifacts', 'search', 'nodes']


class CapabilityDescriptor(Contract):
    schema_version: Literal['1'] = '1'
    processors: tuple[str, ...] = ()
    indexers: tuple[str, ...] = ()
    media_types: tuple[str, ...] = ()
    transfer_modes: tuple[str, ...] = ()
    max_upload_bytes: int = Field(ge=0)
    max_read_bytes: int = Field(gt=0)
    max_page_size: int = Field(gt=0, le=1000)
