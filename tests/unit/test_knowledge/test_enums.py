from enum import StrEnum

from modules.knowledge.domain.enums import CollectionStatus, DocumentStatus, ParserType


class TestCollectionStatus:
    def test_values(self):
        assert CollectionStatus.ACTIVE == "active"
        assert CollectionStatus.ARCHIVED == "archived"
        assert CollectionStatus.DELETED == "deleted"

    def test_is_strenum(self):
        assert issubclass(CollectionStatus, StrEnum)

    def test_members(self):
        assert len(CollectionStatus) == 3


class TestDocumentStatus:
    def test_values(self):
        assert DocumentStatus.UPLOADED == "uploaded"
        assert DocumentStatus.PARSING == "parsing"
        assert DocumentStatus.CHUNKING == "chunking"
        assert DocumentStatus.INDEXING == "indexing"
        assert DocumentStatus.READY == "ready"
        assert DocumentStatus.FAILED == "failed"
        assert DocumentStatus.DELETED == "deleted"

    def test_is_strenum(self):
        assert issubclass(DocumentStatus, StrEnum)

    def test_members(self):
        assert len(DocumentStatus) == 7


class TestParserType:
    def test_values(self):
        assert ParserType.PDF == "pdf"
        assert ParserType.DOCX == "docx"
        assert ParserType.MD == "md"
        assert ParserType.HTML == "html"
        assert ParserType.TEXT == "text"
        assert ParserType.CSV == "csv"
        assert ParserType.JSON == "json"
        assert ParserType.IMAGE == "image"

    def test_is_strenum(self):
        assert issubclass(ParserType, StrEnum)

    def test_members(self):
        assert len(ParserType) == 8
