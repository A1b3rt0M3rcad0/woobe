import uuid

from modules.knowledge.domain.errors import (
    ChunkNotFoundError,
    CollectionNotFoundError,
    DocumentNotFoundError,
    DuplicateCollectionError,
)
from shared.domain.errors import ConflictError, NotFoundError


class TestCollectionNotFoundError:
    def test_inheritance(self):
        e = CollectionNotFoundError(collection_id=uuid.uuid4())
        assert isinstance(e, NotFoundError)

    def test_message(self):
        cid = uuid.uuid4()
        e = CollectionNotFoundError(collection_id=cid)
        assert str(e) == f"Document collection not found: {cid}"
        assert e.collection_id == cid


class TestDocumentNotFoundError:
    def test_inheritance(self):
        e = DocumentNotFoundError(document_id=uuid.uuid4())
        assert isinstance(e, NotFoundError)

    def test_message(self):
        did = uuid.uuid4()
        e = DocumentNotFoundError(document_id=did)
        assert str(e) == f"Document not found: {did}"
        assert e.document_id == did


class TestChunkNotFoundError:
    def test_inheritance(self):
        e = ChunkNotFoundError(chunk_id=uuid.uuid4())
        assert isinstance(e, NotFoundError)

    def test_message(self):
        cid = uuid.uuid4()
        e = ChunkNotFoundError(chunk_id=cid)
        assert str(e) == f"Document chunk not found: {cid}"
        assert e.chunk_id == cid


class TestDuplicateCollectionError:
    def test_inheritance(self):
        e = DuplicateCollectionError(name="test", project_id=uuid.uuid4())
        assert isinstance(e, ConflictError)

    def test_message(self):
        pid = uuid.uuid4()
        e = DuplicateCollectionError(name="My Collection", project_id=pid)
        assert str(e) == f"Collection 'My Collection' already exists in project {pid}"
        assert e.name == "My Collection"
        assert e.project_id == pid
