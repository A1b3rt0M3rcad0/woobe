from __future__ import annotations

from enum import StrEnum, auto


class CollectionStatus(StrEnum):
    ACTIVE = auto()
    ARCHIVED = auto()
    DELETED = auto()


class DocumentStatus(StrEnum):
    UPLOADED = auto()
    PARSING = auto()
    CHUNKING = auto()
    INDEXING = auto()
    READY = auto()
    FAILED = auto()
    DELETED = auto()


class ParserType(StrEnum):
    PDF = auto()
    DOCX = auto()
    MD = auto()
    HTML = auto()
    TEXT = auto()
    CSV = auto()
    JSON = auto()
    IMAGE = auto()


class KnowledgeVersionStatus(StrEnum):
    DRAFT = auto()
    RELEASED = auto()
    ARCHIVED = auto()
