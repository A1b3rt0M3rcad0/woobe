"""Transport-independent identities and invariants for persistent artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
import re
import unicodedata


ID_PATTERN = r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}"
SHA256_PATTERN = r"[0-9a-f]{64}"


def opaque_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(ID_PATTERN, value):
        raise ValueError("Invalid opaque artifact identifier")
    return value


def sha256_digest(value: str) -> str:
    if not re.fullmatch(SHA256_PATTERN, value):
        raise ValueError("Expected a lowercase SHA-256 digest")
    return value


def logical_path(value: str) -> str:
    if (not value or len(value) > 1024 or value != unicodedata.normalize('NFC', value)
            or '\\' in value or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError("Invalid logical artifact path")
    if any(part in {'', '.', '..'} or len(part.encode('utf-8')) > 255
           for part in value.split('/')):
        raise ValueError("Invalid logical artifact path")
    return value


class Environment(StrEnum):
    DRAFT = 'draft'
    STAGING = 'staging'
    PRODUCTION = 'production'


class WorkspaceStatus(StrEnum):
    ACTIVE = 'active'
    ARCHIVED = 'archived'
    DELETION_PENDING = 'deletion_pending'
    PURGED = 'purged'


class UploadStatus(StrEnum):
    CREATED = 'created'
    UPLOADING = 'uploading'
    VERIFYING = 'verifying'
    COMMITTED = 'committed'
    FAILED = 'failed'
    ABORTED = 'aborted'
    EXPIRED = 'expired'


class JobStatus(StrEnum):
    QUEUED = 'queued'
    RUNNING = 'running'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    CANCEL_REQUESTED = 'cancel_requested'
    CANCELLED = 'cancelled'
    UNCERTAIN = 'uncertain'


class Coverage(StrEnum):
    COMPLETE = 'complete'
    PARTIAL = 'partial'
    NEEDS_OCR = 'needs_ocr'
    UNSUPPORTED = 'unsupported'


class Action(StrEnum):
    READ = 'read'
    SEARCH = 'search'
    WRITE = 'write'
    DELETE = 'delete'
    PROCESS = 'process'
    TRANSFER = 'transfer'
    MANAGE = 'manage'


class ErrorCode(StrEnum):
    ACCESS_DENIED = 'ARTIFACT_ACCESS_DENIED'
    SOURCE_UNAVAILABLE = 'SOURCE_UNAVAILABLE'
    WORKSPACE_BINDING_CONFLICT = 'WORKSPACE_BINDING_CONFLICT'
    REVISION_CONFLICT = 'ARTIFACT_REVISION_CONFLICT'
    WORKSPACE_REVISION_CONFLICT = 'WORKSPACE_REVISION_CONFLICT'
    PATH_CONFLICT = 'ARTIFACT_PATH_CONFLICT'
    IDEMPOTENCY_CONFLICT = 'ARTIFACT_IDEMPOTENCY_CONFLICT'
    QUOTA_EXCEEDED = 'QUOTA_EXCEEDED'
    UPLOAD_INTEGRITY_MISMATCH = 'UPLOAD_INTEGRITY_MISMATCH'
    UPLOAD_OFFSET_CONFLICT = 'UPLOAD_OFFSET_CONFLICT'
    UPLOAD_EXPIRED = 'UPLOAD_EXPIRED'
    PROCESSOR_UNAVAILABLE = 'PROCESSOR_UNAVAILABLE'
    REPRESENTATION_NOT_READY = 'REPRESENTATION_NOT_READY'
    FILE_TRANSFER_UNSUPPORTED = 'FILE_TRANSFER_UNSUPPORTED'
    EXTERNAL_OPERATION_UNCERTAIN = 'EXTERNAL_OPERATION_UNCERTAIN'
    INVALID_CURSOR = 'ARTIFACT_INVALID_CURSOR'
    INVALID_RANGE = 'ARTIFACT_INVALID_RANGE'
    LIMIT_EXCEEDED = 'ARTIFACT_LIMIT_EXCEEDED'
    STORAGE_UNAVAILABLE = 'ARTIFACT_STORAGE_UNAVAILABLE'


class ArtifactError(Exception):
    """Safe public error; adapter internals must not be included in messages."""

    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = ErrorCode(code)
        self.retryable = retryable


@dataclass(frozen=True)
class Scope:
    project_id: str
    environment: Environment

    def __post_init__(self):
        opaque_id(self.project_id)
        object.__setattr__(self, 'environment', Environment(self.environment))


@dataclass(frozen=True)
class ArtifactRef:
    artifact_id: str
    revision_id: str

    def __post_init__(self):
        opaque_id(self.artifact_id)
        opaque_id(self.revision_id)


def artifact_object_key(scope: Scope, workspace_id: str, reference: ArtifactRef) -> str:
    opaque_id(workspace_id)
    return (f'projects/{scope.project_id}/environments/{scope.environment.value}/'
            f'artifact-workspaces/{workspace_id}/artifacts/{reference.artifact_id}/'
            f'revisions/{reference.revision_id}/original')


@dataclass(frozen=True)
class Locator:
    block_id: str | None = None
    page_index: int | None = None
    page_number: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    byte_start: int | None = None
    byte_end: int | None = None
    char_space: str = 'original_decoded_text'
    source_encoding: str | None = None
    text_normalization: str = 'none'

    def __post_init__(self):
        if self.block_id is not None:
            opaque_id(self.block_id)
        if self.page_index is not None and self.page_index < 0:
            raise ValueError('Physical pages are zero-based')
        if self.page_number is not None:
            if self.page_index is None or self.page_number != self.page_index + 1:
                raise ValueError('Display page must match its physical page')
        for start, end, minimum in ((self.line_start, self.line_end, 1),
                                    (self.char_start, self.char_end, 0),
                                    (self.byte_start, self.byte_end, 0)):
            if (start is None) != (end is None):
                raise ValueError('Locator intervals need both endpoints')
            if start is not None and (start < minimum or end < start):
                raise ValueError('Invalid locator interval')
        if self.char_space not in {'original_decoded_text', 'page_extracted_text', 'canonical_block_text'}:
            raise ValueError('Unknown character coordinate space')
        if self.source_encoding not in {None, 'utf-8', 'utf-16-le', 'utf-16-be', 'latin-1'}:
            raise ValueError('Unsupported source locator encoding')
        if self.text_normalization not in {'none', 'lf'}:
            raise ValueError('Unsupported text locator normalization')
        if self.bbox is not None and (
            self.page_index is None or len(self.bbox) != 4
            or not all(0 <= x <= 1 for x in self.bbox)
            or self.bbox[0] > self.bbox[2] or self.bbox[1] > self.bbox[3]
        ):
            raise ValueError('Bounding box requires a page and normalized coordinates')


@dataclass(frozen=True)
class SourceRef:
    artifact_id: str
    revision_id: str
    source_sha256: str
    representation_set_id: str | None = None
    document_index_id: str | None = None
    node_id: str | None = None
    locator: Locator | None = None
    excerpt_sha256: str | None = None

    def __post_init__(self):
        if (self.locator is not None and self.locator.char_start is not None
            and self.locator.char_space != 'original_decoded_text' and self.representation_set_id is None):
            raise ValueError('Derived character coordinates require a representation generation')
        ArtifactRef(self.artifact_id, self.revision_id)
        sha256_digest(self.source_sha256)
        for value in (self.representation_set_id, self.document_index_id, self.node_id):
            if value is not None:
                opaque_id(value)
        if self.document_index_id is not None and self.representation_set_id is None:
            raise ValueError('An index reference requires its representation generation')
        if self.node_id is not None and self.document_index_id is None:
            raise ValueError('A node reference requires its exact index')
        if self.excerpt_sha256 is not None:
            sha256_digest(self.excerpt_sha256)


@dataclass(frozen=True)
class Workspace:
    id: str
    scope: Scope
    external_namespace: str
    external_key: str
    name: str
    storage_profile: str = 'local'
    status: WorkspaceStatus = WorkspaceStatus.ACTIVE
    version: int = 1
    catalog_version: int = 0
    quota_bytes: int = 1_073_741_824
    used_bytes: int = 0
    reserved_bytes: int = 0
    retention_days: int = 30
    labels: tuple[tuple[str, str], ...] = ()
    default_profile_id: str | None = None
    default_profile_revision: int | None = None

    def __post_init__(self):
        opaque_id(self.id)
        opaque_id(self.storage_profile)
        object.__setattr__(self, 'status', WorkspaceStatus(self.status))
        for name in ('external_namespace', 'external_key', 'name'):
            value = getattr(self, name)
            if not value.strip() or len(value) > 255 or '\x00' in value:
                raise ValueError(f'Invalid workspace {name}')
        if (self.default_profile_id is None) != (self.default_profile_revision is None):
            raise ValueError('Default processing profile requires identity and revision')
        if self.default_profile_id is not None:
            opaque_id(self.default_profile_id)
            if self.default_profile_revision < 1:
                raise ValueError('Default profile revision must be positive')
        if self.version < 1 or self.catalog_version < 0 or self.retention_days < 0:
            raise ValueError('Invalid workspace version/retention')
        if min(self.quota_bytes, self.used_bytes, self.reserved_bytes) < 0:
            raise ValueError('Negative quota accounting')
        if self.used_bytes + self.reserved_bytes > self.quota_bytes:
            raise ValueError('Quota accounting exceeds its limit')
        if len(self.labels) > 32 or len(dict(self.labels)) != len(self.labels):
            raise ValueError('Invalid workspace labels')
        for key, value in self.labels:
            if not key or len(key) > 64 or len(value) > 1024 or '\x00' in key + value:
                raise ValueError('Invalid workspace label')


@dataclass(frozen=True)
class Artifact:
    id: str
    workspace_id: str
    path: str
    kind: str = 'file'
    revision_id: str | None = None
    version: int = 1
    deleted: bool = False

    def __post_init__(self):
        opaque_id(self.id)
        opaque_id(self.workspace_id)
        logical_path(self.path)
        if self.kind not in {'file', 'directory'} or self.version < 1:
            raise ValueError('Invalid artifact kind/version')
        if self.revision_id is not None:
            opaque_id(self.revision_id)
        if self.kind == 'directory' and self.revision_id is not None:
            raise ValueError('Directories do not have content revisions')


@dataclass(frozen=True)
class Revision:
    id: str
    artifact_id: str
    object_key: str
    content_type: str
    size_bytes: int
    sha256: str
    origin: str
    producer_id: str | None = None
    storage_version_id: str | None = None
    operation_id: str | None = None
    run_id: str | None = None
    node_id: str | None = None

    def __post_init__(self):
        ArtifactRef(self.artifact_id, self.id)
        logical_path(self.object_key)
        sha256_digest(self.sha256)
        if self.size_bytes < 0 or '/' not in self.content_type:
            raise ValueError('Invalid revision size or MIME')
        if self.origin not in {'upload', 'application', 'agent', 'tool', 'processing', 'copy'}:
            raise ValueError('Unknown revision provenance')
        for value in (self.operation_id, self.run_id, self.node_id):
            if value is not None:
                opaque_id(value)
        if self.node_id is not None and self.run_id is None:
            raise ValueError('Node provenance requires a Run identity')


@dataclass(frozen=True)
class DocumentBlock:
    id: str
    kind: str
    text: str
    locator: Locator
    inferred: bool = False
    heading_level: int | None = None
    language: str | None = None
    data_json: str | None = None
    title: str | None = None

    def __post_init__(self):
        opaque_id(self.id)
        if self.kind not in {'heading', 'paragraph', 'table', 'figure', 'page', 'warning', 'code', 'list', 'json'}:
            raise ValueError('Unknown canonical block kind')
        if self.heading_level is not None and (self.kind != 'heading' or not 1 <= self.heading_level <= 6):
            raise ValueError('Heading level requires a real heading')
        if self.language is not None and (self.kind != 'code' or len(self.language) > 64):
            raise ValueError('Language hints belong only to code blocks')


@dataclass(frozen=True)
class CanonicalDocument:
    revision: ArtifactRef
    blocks: tuple[DocumentBlock, ...]
    coverage: Coverage
    diagnostics: tuple[str, ...] = ()
    source_encoding: str | None = None
    source_size_bytes: int | None = None
    source_character_count: int | None = None
    text_normalization: str = 'none'
    trust_level: str = 'untrusted_source'
    page_count: int | None = None

    def __post_init__(self):
        if self.source_encoding not in {None, 'utf-8', 'utf-16-le', 'utf-16-be', 'latin-1'}:
            raise ValueError('Unsupported canonical source encoding')
        if self.text_normalization not in {'none', 'lf'}:
            raise ValueError('Unsupported canonical text normalization')
        if self.trust_level != 'untrusted_source':
            raise ValueError('Document source content cannot become trusted instructions')
        if self.source_size_bytes is not None and self.source_size_bytes < 0:
            raise ValueError('Invalid source byte length')
        if self.source_character_count is not None and self.source_character_count < 0:
            raise ValueError('Invalid source character count')
        if self.page_count is not None and self.page_count < 0:
            raise ValueError('Invalid physical page count')
        object.__setattr__(self, 'coverage', Coverage(self.coverage))
        if len({block.id for block in self.blocks}) != len(self.blocks):
            raise ValueError('Duplicate block IDs in representation')
        if not self.blocks and self.coverage == Coverage.COMPLETE:
            raise ValueError('An empty extraction cannot claim complete coverage')


@dataclass(frozen=True)
class DocumentNode:
    id: str
    title: str
    block_ids: tuple[str, ...]
    parent_id: str | None = None
    summary: str | None = None


@dataclass(frozen=True)
class DocumentIndex:
    id: str
    representation_set_id: str
    engine: str
    engine_version: str
    nodes: tuple[DocumentNode, ...]

    def __post_init__(self):
        opaque_id(self.id)
        opaque_id(self.representation_set_id)
        by_id = {node.id: node for node in self.nodes}
        if not self.engine or not self.engine_version or len(by_id) != len(self.nodes):
            raise ValueError('Invalid document index identity')
        for node in self.nodes:
            opaque_id(node.id)
            seen = {node.id}
            parent = node.parent_id
            while parent is not None:
                if parent in seen or parent not in by_id:
                    raise ValueError('Invalid index parent or cycle')
                seen.add(parent)
                parent = by_id[parent].parent_id


@dataclass(frozen=True)
class ProcessingProfile:
    id: str
    revision: int
    processor: str
    processor_version: str
    indexer: str = 'structural'
    indexer_version: str = '1'
    max_bytes: int = 52_428_800
    max_pages: int = 500
    timeout_seconds: int = 120
    ocr_enabled: bool = False
    model_enrichment: bool = False
    options: tuple[tuple[str, str], ...] = ()

    def __post_init__(self):
        opaque_id(self.id)
        if min(self.revision, self.max_bytes, self.max_pages, self.timeout_seconds) < 1:
            raise ValueError('Processing limits and revision must be positive')
        if not all((self.processor, self.processor_version, self.indexer, self.indexer_version)):
            raise ValueError('Processing components must be versioned')


@dataclass(frozen=True)
class ProcessingJob:
    id: str
    workspace_id: str
    revision: ArtifactRef
    profile_id: str
    profile_revision: int
    status: JobStatus = JobStatus.QUEUED
    attempt: int = 0
    fencing_token: int = 0
    lease_until: datetime | None = None
    completed_stages: tuple[str, ...] = ()

    def __post_init__(self):
        for value in (self.id, self.workspace_id, self.profile_id):
            opaque_id(value)
        object.__setattr__(self, 'status', JobStatus(self.status))
        if self.profile_revision < 1 or self.attempt < 0 or self.fencing_token < 0:
            raise ValueError('Invalid job revision or fencing state')
        if self.lease_until is not None and self.lease_until.tzinfo is None:
            raise ValueError('Job leases require an explicit timezone')


@dataclass(frozen=True)
class RepresentationSet:
    id: str
    revision: ArtifactRef
    profile_id: str
    profile_revision: int
    document: CanonicalDocument
    index: DocumentIndex
    published_catalog_version: int


@dataclass(frozen=True)
class SourceManifest:
    workspace_id: str
    catalog_version: int
    sources: tuple[SourceRef, ...] = ()

    def __post_init__(self):
        opaque_id(self.workspace_id)
        if self.catalog_version < 0:
            raise ValueError('Invalid pinned catalog version')


@dataclass(frozen=True)
class WorkspaceGrant:
    id: str
    principal_id: str
    scope: Scope
    actions: frozenset[Action]
    workspace_id: str | None = None
    external_namespace: str | None = None
    revision: int = 1
    expires_at: datetime | None = None
    revoked: bool = False

    def __post_init__(self):
        opaque_id(self.id)
        opaque_id(self.principal_id)
        if (self.workspace_id is None) == (self.external_namespace is None):
            raise ValueError('A grant requires exactly one workspace/namespace selector')
        if self.workspace_id is not None:
            opaque_id(self.workspace_id)
        if self.external_namespace is not None and not self.external_namespace.strip():
            raise ValueError('A namespace grant cannot have an empty selector')
        if self.revision < 1 or not self.actions or any(action not in Action for action in self.actions):
            raise ValueError('Invalid grant actions/revision')
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError('Grant expiration requires an explicit timezone')


@dataclass(frozen=True)
class ArtifactHeadHistory:
    artifact_id: str
    workspace_id: str
    from_catalog_version: int
    until_catalog_version: int | None
    path: str
    revision_id: str | None
    deleted: bool = False

    def __post_init__(self):
        opaque_id(self.artifact_id)
        opaque_id(self.workspace_id)
        logical_path(self.path)
        if self.from_catalog_version < 1 or (
            self.until_catalog_version is not None
            and self.until_catalog_version <= self.from_catalog_version
        ):
            raise ValueError('Catalog visibility intervals are nonempty and half-open')


@dataclass(frozen=True)
class UploadIntent:
    id: str
    workspace_id: str
    operation_id: str
    request_fingerprint: str
    expected_size: int
    expected_sha256: str
    content_type: str
    offset: int = 0
    status: UploadStatus = UploadStatus.CREATED
    receipt: ArtifactRef | None = None

    def __post_init__(self):
        for value in (self.id, self.workspace_id, self.operation_id):
            opaque_id(value)
        sha256_digest(self.request_fingerprint)
        sha256_digest(self.expected_sha256)
        object.__setattr__(self, 'status', UploadStatus(self.status))
        if not 0 <= self.offset <= self.expected_size:
            raise ValueError('Invalid upload offset')
        if (self.status == UploadStatus.COMMITTED) != (self.receipt is not None):
            raise ValueError('Only committed uploads have revision receipts')


@dataclass(frozen=True)
class ArtifactRepresentation:
    id: str
    representation_set_id: str
    object_key: str
    kind: str
    sha256: str
    size_bytes: int
    content_type: str

    def __post_init__(self):
        opaque_id(self.id)
        opaque_id(self.representation_set_id)
        logical_path(self.object_key)
        sha256_digest(self.sha256)
        if self.size_bytes < 0 or self.kind not in {
            'markdown', 'structure', 'source_map', 'table', 'figure', 'rendering', 'summary',
        }:
            raise ValueError('Invalid representation kind/size')


@dataclass(frozen=True)
class RuntimeArtifactBinding:
    workspace_id: str
    scope: Scope
    catalog_version: int
    actions: frozenset[Action]
    binding_scope: str

    def __post_init__(self):
        opaque_id(self.workspace_id)
        if self.catalog_version < 0 or self.binding_scope not in {'session', 'run'}:
            raise ValueError('Invalid runtime artifact binding')


@dataclass(frozen=True)
class TransferReceipt:
    id: str
    operation_id: str
    input_refs: tuple[ArtifactRef, ...]
    state: str
    output_refs: tuple[ArtifactRef, ...] = ()

    def __post_init__(self):
        opaque_id(self.id)
        opaque_id(self.operation_id)
        if self.state not in {'pending', 'completed', 'failed', 'uncertain'}:
            raise ValueError('Invalid transfer state')


@dataclass(frozen=True)
class Page[T]:
    items: tuple[T, ...]
    has_more: bool = False
    next_cursor: str | None = None
    truncated: bool = False
    diagnostics: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if self.has_more != (self.next_cursor is not None):
            raise ValueError('Pagination must expose an explicit continuation')
