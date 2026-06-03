import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from modules.knowledge.domain.entities import Document, DocumentCollection
from modules.knowledge.domain.enums import CollectionStatus, DocumentStatus, ParserType
from modules.knowledge.service.dtos import (
    CreateCollectionInput,
    CreateCollectionOutput,
    SearchChunksInput,
    SearchChunksOutput,
    UploadDocumentInput,
    UploadDocumentOutput,
)
from modules.knowledge.service.use_cases import (
    CreateCollectionUseCase,
    SearchChunksUseCase,
    UploadDocumentUseCase,
)


class TestCreateCollectionUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        pid = uuid.uuid4()
        now = datetime.now(timezone.utc)
        input_dto = CreateCollectionInput(project_id=pid, name="Test Collection")

        collection = DocumentCollection(
            id=uuid.uuid4(),
            project_id=pid,
            name="Test Collection",
            status=CollectionStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )

        mock_repo = mocker.AsyncMock()
        mock_repo.create.return_value = collection

        mock_session = mocker.MagicMock()

        uc = CreateCollectionUseCase(session=mock_session, repo=mock_repo)
        result = await uc.execute(input_dto)

        assert isinstance(result, CreateCollectionOutput)
        assert result.id == collection.id
        assert result.project_id == pid
        assert result.name == "Test Collection"
        assert result.status == CollectionStatus.ACTIVE

        mock_repo.create.assert_awaited_once()
        args, _ = mock_repo.create.await_args
        created_collection = args[0]
        assert created_collection.project_id == pid
        assert created_collection.name == "Test Collection"

        mock_session.add.assert_called_once()
        event = mock_session.add.call_args[0][0]
        assert event.aggregate_type == "document_collection"
        assert event.event_type == "knowledge.collection.created"
        assert event.payload["name"] == "Test Collection"

    @pytest.mark.asyncio
    async def test_repo_create_called_with_correct_entity(self, mocker):
        pid = uuid.uuid4()
        input_dto = CreateCollectionInput(project_id=pid, name="My Collection")

        mock_repo = mocker.AsyncMock()
        mock_repo.create.return_value = DocumentCollection(
            id=uuid.uuid4(),
            project_id=pid,
            name="My Collection",
            status=CollectionStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_session = mocker.MagicMock()

        uc = CreateCollectionUseCase(session=mock_session, repo=mock_repo)
        await uc.execute(input_dto)

        mock_repo.create.assert_awaited_once()
        args, _ = mock_repo.create.await_args
        entity = args[0]
        assert entity.project_id == pid
        assert entity.name == "My Collection"


class TestUploadDocumentUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        pid = uuid.uuid4()
        cid = uuid.uuid4()
        now = datetime.now(timezone.utc)

        input_dto = UploadDocumentInput(
            project_id=pid,
            collection_id=cid,
            title="doc.pdf",
            file_name="doc.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            storage_key="uploads/doc.pdf",
            parser=ParserType.PDF,
        )

        created_doc = Document(
            id=uuid.uuid4(),
            project_id=pid,
            collection_id=cid,
            title="doc.pdf",
            file_name="doc.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            storage_key="uploads/doc.pdf",
            parser=ParserType.PDF,
            status=DocumentStatus.UPLOADED,
            created_at=now,
            updated_at=now,
        )

        mock_collection_repo = mocker.AsyncMock()
        mock_collection_repo.get_by_id.return_value = mocker.MagicMock()
        mock_doc_repo = mocker.AsyncMock()
        mock_doc_repo.create.return_value = created_doc
        mock_session = mocker.MagicMock()

        uc = UploadDocumentUseCase(
            session=mock_session,
            doc_repo=mock_doc_repo,
            collection_repo=mock_collection_repo,
        )
        result = await uc.execute(input_dto)

        assert isinstance(result, UploadDocumentOutput)
        assert result.id == created_doc.id
        assert result.title == "doc.pdf"
        assert result.status == DocumentStatus.UPLOADED
        assert result.parser == ParserType.PDF

        mock_doc_repo.create.assert_awaited_once()
        mock_session.add.assert_called_once()
        event = mock_session.add.call_args[0][0]
        assert event.event_type == "knowledge.document.uploaded"
        assert event.payload["file_name"] == "doc.pdf"

    @pytest.mark.asyncio
    async def test_document_entity_constructed_correctly(self, mocker):
        pid = uuid.uuid4()
        cid = uuid.uuid4()

        input_dto = UploadDocumentInput(
            project_id=pid,
            collection_id=cid,
            title="report.pdf",
            file_name="report.pdf",
            content_type="application/pdf",
            size_bytes=2048,
            storage_key="x/report.pdf",
            parser=ParserType.PDF,
        )

        mock_collection_repo = mocker.AsyncMock()
        mock_collection_repo.get_by_id.return_value = mocker.MagicMock()
        mock_doc_repo = mocker.AsyncMock()
        mock_doc_repo.create.return_value = Document(
            id=uuid.uuid4(),
            project_id=pid,
            collection_id=cid,
            title="report.pdf",
            file_name="report.pdf",
            content_type="application/pdf",
            size_bytes=2048,
            storage_key="x/report.pdf",
            parser=ParserType.PDF,
            status=DocumentStatus.UPLOADED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        mock_session = mocker.MagicMock()

        uc = UploadDocumentUseCase(
            session=mock_session,
            doc_repo=mock_doc_repo,
            collection_repo=mock_collection_repo,
        )
        await uc.execute(input_dto)

        mock_doc_repo.create.assert_awaited_once()
        args, _ = mock_doc_repo.create.await_args
        entity = args[0]
        assert entity.project_id == pid
        assert entity.collection_id == cid
        assert entity.title == "report.pdf"
        assert entity.status == DocumentStatus.UPLOADED


class TestSearchChunksUseCase:
    @pytest.mark.asyncio
    async def test_no_results(self, mocker):
        input_dto = SearchChunksInput(
            collection_id=uuid.uuid4(),
            embedding=[0.1],
            limit=10,
            threshold=0.9,
        )

        mock_repo = mocker.AsyncMock()
        mock_repo.search_similar.return_value = []

        uc = SearchChunksUseCase(repo=mock_repo)
        result = await uc.execute(input_dto)

        assert isinstance(result, SearchChunksOutput)
        assert result.results == []
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_correct_defaults_passed_to_repo(self, mocker):
        input_dto = SearchChunksInput(
            collection_id=uuid.uuid4(),
            embedding=[0.5],
        )

        mock_repo = mocker.AsyncMock()
        mock_repo.search_similar.return_value = []

        uc = SearchChunksUseCase(repo=mock_repo)
        await uc.execute(input_dto)

        mock_repo.search_similar.assert_awaited_once()
        _, kwargs = mock_repo.search_similar.await_args
        assert kwargs["limit"] == 10
        assert kwargs["threshold"] == 0.7

    @pytest.mark.asyncio
    async def test_success(self, mocker):
        cid = uuid.uuid4()
        embedding = [0.1, 0.2, 0.3]
        input_dto = SearchChunksInput(
            collection_id=cid,
            embedding=embedding,
            limit=5,
            threshold=0.8,
        )

        chunk = MagicMock()
        chunk.id = uuid.uuid4()
        chunk.collection_id = cid
        chunk.content = "matched content"
        chunk.chunk_index = 0
        chunk.token_count = 50
        chunk.page_number = 1
        chunk.section_title = "Results"
        chunk.data = {"source": "pdf"}
        chunk.data = {"source": "pdf"}

        mock_repo = mocker.AsyncMock()
        mock_repo.search_similar.return_value = [(chunk, 0.92)]

        uc = SearchChunksUseCase(repo=mock_repo)
        result = await uc.execute(input_dto)

        assert isinstance(result, SearchChunksOutput)
        assert len(result.results) == 1
        assert result.total == 1
        assert result.results[0].content == "matched content"
        assert result.results[0].chunk_index == 0

        mock_repo.search_similar.assert_awaited_once_with(
            embedding=embedding,
            collection_id=cid,
            limit=5,
            threshold=0.8,
        )
