import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from modules.knowledge.domain.enums import CollectionStatus, DocumentStatus, ParserType
from modules.knowledge.service.dtos import (
    CreateCollectionInput,
    CreateCollectionOutput,
    DocumentChunkOutput,
    SearchChunksInput,
    SearchChunksOutput,
    UploadDocumentInput,
    UploadDocumentOutput,
)


class TestCreateCollectionInput:
    def test_valid(self):
        pid = uuid.uuid4()
        dto = CreateCollectionInput(project_id=pid, name="Test Collection")
        assert dto.project_id == pid
        assert dto.name == "Test Collection"
        assert dto.description is None

    def test_with_description(self):
        dto = CreateCollectionInput(
            project_id=uuid.uuid4(),
            name="Docs",
            description="A collection of docs",
        )
        assert dto.description == "A collection of docs"

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError):
            CreateCollectionInput(project_id=uuid.uuid4(), name="")

    def test_name_too_long_raises(self):
        with pytest.raises(ValidationError):
            CreateCollectionInput(project_id=uuid.uuid4(), name="x" * 256)


class TestCreateCollectionOutput:
    def test_valid(self):
        now = datetime.now(timezone.utc)
        pid = uuid.uuid4()
        cid = uuid.uuid4()
        dto = CreateCollectionOutput(
            id=cid,
            project_id=pid,
            name="Test",
            description=None,
            status=CollectionStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        assert dto.id == cid
        assert dto.name == "Test"
        assert dto.status == CollectionStatus.ACTIVE


class TestUploadDocumentInput:
    def test_valid(self):
        pid = uuid.uuid4()
        cid = uuid.uuid4()
        dto = UploadDocumentInput(
            project_id=pid,
            collection_id=cid,
            title="doc.pdf",
            file_name="doc.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            storage_key="uploads/doc.pdf",
            parser=ParserType.PDF,
        )
        assert dto.title == "doc.pdf"
        assert dto.parser == ParserType.PDF
        assert dto.size_bytes == 1024

    def test_default_parser(self):
        dto = UploadDocumentInput(
            project_id=uuid.uuid4(),
            collection_id=uuid.uuid4(),
            title="file.txt",
            file_name="file.txt",
            content_type="text/plain",
            size_bytes=500,
            storage_key="file.txt",
        )
        assert dto.parser == ParserType.TEXT

    def test_negative_size_raises(self):
        with pytest.raises(ValidationError):
            UploadDocumentInput(
                project_id=uuid.uuid4(),
                collection_id=uuid.uuid4(),
                title="doc.pdf",
                file_name="doc.pdf",
                content_type="application/pdf",
                size_bytes=-1,
                storage_key="x",
            )

    def test_empty_title_raises(self):
        with pytest.raises(ValidationError):
            UploadDocumentInput(
                project_id=uuid.uuid4(),
                collection_id=uuid.uuid4(),
                title="",
                file_name="doc.pdf",
                content_type="application/pdf",
                size_bytes=100,
                storage_key="x",
            )


class TestUploadDocumentOutput:
    def test_valid(self):
        now = datetime.now(timezone.utc)
        dto = UploadDocumentOutput(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            collection_id=uuid.uuid4(),
            title="doc.pdf",
            file_name="doc.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            storage_key="x",
            parser=ParserType.PDF,
            status=DocumentStatus.UPLOADED,
            created_at=now,
            updated_at=now,
        )
        assert dto.status == DocumentStatus.UPLOADED
        assert dto.parser == ParserType.PDF


class TestDocumentChunkOutput:
    def test_valid(self):
        dto = DocumentChunkOutput(
            id=uuid.uuid4(),
            content="chunk content",
            chunk_index=0,
            token_count=50,
            page_number=1,
            section_title="Intro",
            data={"key": "val"},
            similarity=0.95,
        )
        assert dto.content == "chunk content"
        assert dto.chunk_index == 0
        assert dto.similarity == 0.95
        assert dto.data == {"key": "val"}

    def test_default_similarity(self):
        dto = DocumentChunkOutput(
            id=uuid.uuid4(),
            content="test",
            chunk_index=0,
            token_count=None,
            page_number=None,
            section_title=None,
            data=None,
        )
        assert dto.similarity is None

    def test_minimal(self):
        dto = DocumentChunkOutput(
            id=uuid.uuid4(),
            content="test",
            chunk_index=0,
            token_count=None,
            page_number=None,
            section_title=None,
            data=None,
        )
        assert dto.token_count is None
        assert dto.page_number is None
        assert dto.section_title is None


class TestSearchChunksInput:
    def test_valid(self):
        cid = uuid.uuid4()
        dto = SearchChunksInput(
            collection_id=cid,
            embedding=[0.1, 0.2, 0.3],
        )
        assert dto.collection_id == cid
        assert dto.embedding == [0.1, 0.2, 0.3]
        assert dto.limit == 10
        assert dto.threshold == 0.7

    def test_custom_limit(self):
        dto = SearchChunksInput(
            collection_id=uuid.uuid4(),
            embedding=[0.1],
            limit=25,
            threshold=0.8,
        )
        assert dto.limit == 25
        assert dto.threshold == 0.8

    def test_limit_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            SearchChunksInput(
                collection_id=uuid.uuid4(),
                embedding=[0.1],
                limit=0,
            )

    def test_threshold_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            SearchChunksInput(
                collection_id=uuid.uuid4(),
                embedding=[0.1],
                threshold=1.5,
            )


class TestSearchChunksOutput:
    def test_valid(self):
        result = DocumentChunkOutput(
            id=uuid.uuid4(),
            content="result",
            chunk_index=0,
            token_count=None,
            page_number=None,
            section_title=None,
            data=None,
        )
        dto = SearchChunksOutput(results=[result], total=1)
        assert len(dto.results) == 1
        assert dto.total == 1

    def test_empty_results(self):
        dto = SearchChunksOutput(results=[], total=0)
        assert dto.results == []
        assert dto.total == 0
