from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import Field

from modules.artifacts.application.contracts.api import Contract, Digest, Identifier, SourceReference
from modules.artifacts.application.contracts.files import FileRequest
from modules.artifacts.application.contracts.jobs import JobLease


@dataclass(frozen=True)
class IndexPhase:
    lease: JobLease
    representation_set_id: str
    index_id: str | None = None
    value: dict | None = None


@dataclass(frozen=True)
class ReadIndex(FileRequest):
    index_id: str


@dataclass(frozen=True)
class ReadIndexNode(ReadIndex):
    node_id: str


@dataclass(frozen=True)
class ListIndexNodes(ReadIndex):
    parent_id: str | None = None
    limit: int = 50
    cursor: str | None = None


class DocumentIndexView(Contract):
    schema_version: Literal['1'] = '1'
    id: Identifier
    workspace_id: Identifier
    artifact_id: Identifier
    revision_id: Identifier
    representation_set_id: Identifier
    source_sha256: Digest
    recipe_fingerprint: Digest
    processing_fingerprint: Digest
    engine: str
    engine_version: str
    status: Literal['ready'] = 'ready'
    tree_kind: Literal['headings', 'canonical', 'pages', 'blocks', 'empty']
    coverage: Literal['complete', 'partial', 'needs_ocr', 'unsupported']
    root_node_id: Identifier
    node_count: int = Field(ge=1, le=110_001)
    source_block_count: int = Field(ge=0, le=100_000)
    max_depth: int = Field(ge=0, le=64)
    manifest_sha256: Digest
    created_at: datetime
    read_only: Literal[True] = True


class DocumentNodeView(Contract):
    schema_version: Literal['1'] = '1'
    id: Identifier
    document_index_id: Identifier
    representation_set_id: Identifier
    parent_id: Identifier | None
    title: str = Field(max_length=512)
    kind: Literal['root', 'section', 'page', 'block']
    ordinal: int = Field(ge=0)
    depth: int = Field(ge=0, le=64)
    children_count: int = Field(ge=0)
    source_ranges: tuple[tuple[int, int], ...]
    source: SourceReference | None
    has_own_text: bool
    inferred: bool = False
    extraction_method: Literal['native', 'ocr', 'model'] | None = None
    read_only: Literal[True] = True


class DocumentNodePage(Contract):
    schema_version: Literal['1'] = '1'
    items: tuple[DocumentNodeView, ...]
    has_more: bool
    next_cursor: str | None = None
    truncated: bool = False
