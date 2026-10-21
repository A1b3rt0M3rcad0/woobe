from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from pydantic import Field

from modules.artifacts.application.contracts.api import Contract, Digest, Identifier, SourceReference
from modules.artifacts.application.contracts.files import FileRequest
from modules.artifacts.application.contracts.jobs import JobLease
from modules.artifacts.domain.models import ArtifactRepresentation, RepresentationSet, logical_path, sha256_digest
from shared.contracts.object_storage import ObjectMetadata, validate_object_key


REPRESENTATION_ROLES = frozenset({'markdown', 'structure', 'source_map', 'table', 'figure',
    'rendering', 'summary', 'outline', 'block_text', 'asset_manifest', 'manifest', 'document_index'})


@dataclass(frozen=True)
class ReserveProcessingObject:
    lease: JobLease
    key: str
    size_bytes: int
    sha256: str
    content_type: str
    role: str

    def __post_init__(self):
        validate_object_key(self.key)
        sha256_digest(self.sha256)
        if self.role not in REPRESENTATION_ROLES or not 0 <= self.size_bytes <= 536_870_912:
            raise ValueError('Invalid processing output declaration')
        if not self.content_type or len(self.content_type) > 255:
            raise ValueError('Invalid processing output media type')


@dataclass(frozen=True)
class RecordProcessingObject:
    declaration: ReserveProcessingObject
    receipt: ObjectMetadata


@dataclass(frozen=True)
class BundlePhase:
    lease: JobLease
    representation_set_id: str | None = None
    value: dict | None = None


@dataclass(frozen=True)
class ReadRepresentation(FileRequest):
    artifact_id: str
    revision_id: str | None = None
    representation_set_id: str | None = None
    entry_id: str | None = None
    run_id: str | None = field(default=None, kw_only=True)
    catalog_version: int | None = field(default=None, kw_only=True)
    output_node_ids: frozenset[str] = field(default_factory=frozenset, kw_only=True)


@dataclass(frozen=True)
class RenderRepresentationPage(FileRequest):
    artifact_id: str
    revision_id: str
    representation_set_id: str
    page_index: int
    dpi: int = 150
    max_pixels: int = 4_000_000

    def __post_init__(self):
        if type(self.page_index) is not int or not 0 <= self.page_index <= 9999:
            raise ValueError('Invalid physical page index')
        if type(self.dpi) is not int or not 72 <= self.dpi <= 300:
            raise ValueError('Invalid page rendering DPI')
        if type(self.max_pixels) is not int or not 1 <= self.max_pixels <= 4_000_000:
            raise ValueError('Invalid page rendering pixel limit')


@dataclass(frozen=True)
class RenderedRepresentationPage:
    content: bytes
    source_sha256: str


@dataclass(frozen=True)
class ListRepresentations(ReadRepresentation):
    limit: int = 50
    cursor: str | None = None
    directory: str = ''


@dataclass(frozen=True)
class RepresentationSnapshot:
    generation: RepresentationSet
    entry: ArtifactRepresentation | None
    storage_profile: str
    public_view: object | None = None


class RepresentationEntryView(Contract):
    schema_version: Literal['1'] = '1'
    id: Identifier
    representation_set_id: Identifier
    path: str = Field(min_length=1, max_length=1024)
    kind: str
    size_bytes: int = Field(ge=0)
    sha256: Digest
    content_type: str
    read_only: Literal[True] = True
    asset_id: Identifier | None = None


class RepresentationSetView(Contract):
    schema_version: Literal['1'] = '1'
    id: Identifier
    workspace_id: Identifier
    artifact_id: Identifier
    revision_id: Identifier
    source_sha256: Digest
    recipe_fingerprint: Digest
    processing_fingerprint: Digest
    manifest_sha256: Digest
    generation_number: int = Field(ge=0)
    status: Literal['ready'] = 'ready'
    coverage: Literal['complete', 'partial', 'needs_ocr', 'unsupported']
    entry_count: int = Field(ge=0)
    block_count: int = Field(ge=0)
    page_count: int = Field(ge=0)
    diagnostics: tuple[str, ...] = ()
    created_at: datetime
    profile_id: Identifier | None = None
    profile_revision: int | None = None


class RepresentationSetPage(Contract):
    schema_version: Literal['1'] = '1'
    items: tuple[RepresentationSetView, ...]
    has_more: bool
    next_cursor: str | None = None
    truncated: bool = False


class RepresentationEntryPage(Contract):
    schema_version: Literal['1'] = '1'
    items: tuple[RepresentationEntryView, ...]
    has_more: bool
    next_cursor: str | None = None
    truncated: bool = False


class SourceReadDefinition(Contract):
    source: SourceReference
    offset: int = Field(default=0, ge=0)
    max_chars: int = Field(default=8192, ge=1, le=65_536)


@dataclass(frozen=True)
class ReadSource(FileRequest):
    definition: SourceReadDefinition
    # Runtime-only provenance fields; public source-read payloads omit them.
    run_id: str | None = None
    catalog_version: int | None = None
    output_node_ids: frozenset[str] = frozenset()


class SourceResolveBatchDefinition(Contract):
    sources: tuple[SourceReference, ...] = Field(min_length=1, max_length=50)
    max_chars: int = Field(default=512, ge=1, le=8192)


@dataclass(frozen=True)
class ResolveSourceBatch(FileRequest):
    definition: SourceResolveBatchDefinition
    run_id: str | None = None
    catalog_version: int | None = None
    output_node_ids: frozenset[str] = frozenset()


class SourceReadView(Contract):
    schema_version: Literal['1'] = '1'
    source: SourceReference
    text: str
    offset: int
    next_offset: int | None
    truncated: bool
    coverage: Literal['complete', 'partial', 'needs_ocr', 'unsupported']
    page_label: str | None = Field(default=None, max_length=128)


class SourceResolveBatchItem(Contract):
    index: int = Field(ge=0, le=49)
    status: Literal['resolved', 'unavailable']
    source: SourceReference
    preview: SourceReadView | None = None


class SourceResolveBatchView(Contract):
    schema_version: Literal['1'] = '1'
    items: tuple[SourceResolveBatchItem, ...] = Field(max_length=50)


class CopyRepresentationDefinition(Contract):
    operation_id: Identifier
    path: str = Field(min_length=1, max_length=1024)


@dataclass(frozen=True)
class CopyRepresentation(ReadRepresentation):
    operation_id: str = ''
    path: str = ''

    def __post_init__(self):
        logical_path(self.path)
