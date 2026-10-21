from dataclasses import dataclass
from typing import Literal

from pydantic import Field

from modules.artifacts.application.contracts.api import Contract, Identifier, SourceReference
from modules.artifacts.application.contracts.files import FileRequest


SearchMode = Literal['text', 'literal']


@dataclass(frozen=True)
class SearchDocuments(FileRequest):
    query: str
    mode: SearchMode = 'text'
    limit: int = 20
    cursor: str | None = None
    catalog_version: int | None = None
    search_version: int | None = None
    after_id: str | None = None
    after_score: int | None = None
    run_id: str | None = None


@dataclass(frozen=True)
class SearchHit:
    cursor_id: str
    score_rank: int
    value: 'ArtifactSearchResult'


@dataclass(frozen=True)
class SearchQueryResult:
    search_version: int
    hits: tuple[SearchHit, ...]


class ArtifactSearchResult(Contract):
    artifact_id: Identifier
    revision_id: Identifier
    path: str = Field(max_length=1024)
    kind: Literal['file'] = 'file'
    match_location: Literal['content', 'path']
    snippet: str = Field(max_length=512)
    coverage: Literal['complete', 'partial', 'needs_ocr', 'unsupported']
    source: SourceReference


class ArtifactSearchPage(Contract):
    schema_version: Literal['1'] = '1'
    query: str = Field(max_length=256)
    mode: SearchMode
    catalog_version: int = Field(ge=0)
    items: tuple[ArtifactSearchResult, ...]
    has_more: bool
    next_cursor: str | None = None
    truncated: bool = False
