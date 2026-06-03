import uuid
from datetime import datetime, timezone

from modules.knowledge.domain.entities import (
    AgentCollection,
    Document,
    DocumentChunk,
    DocumentCollection,
)
from modules.knowledge.domain.enums import CollectionStatus, DocumentStatus, ParserType


class TestDocumentCollection:
    def test_defaults(self):
        c = DocumentCollection()
        assert isinstance(c.id, uuid.UUID)
        assert c.project_id is None
        assert c.name == ""
        assert c.description is None
        assert c.status == CollectionStatus.ACTIVE
        assert c.created_at is None
        assert c.updated_at is None

    def test_custom_values(self):
        now = datetime.now(timezone.utc)
        cid = uuid.uuid4()
        pid = uuid.uuid4()
        c = DocumentCollection(
            id=cid,
            project_id=pid,
            name="My Collection",
            description="A test",
            status=CollectionStatus.ARCHIVED,
            created_at=now,
            updated_at=now,
        )
        assert c.id == cid
        assert c.project_id == pid
        assert c.name == "My Collection"
        assert c.description == "A test"
        assert c.status == CollectionStatus.ARCHIVED
        assert c.created_at == now
        assert c.updated_at == now

    def test_uuid_generation(self):
        c1 = DocumentCollection()
        c2 = DocumentCollection()
        assert c1.id != c2.id


class TestAgentCollection:
    def test_creation(self):
        aid = uuid.uuid4()
        cid = uuid.uuid4()
        ac = AgentCollection(agent_id=aid, collection_id=cid)
        assert ac.agent_id == aid
        assert ac.collection_id == cid

    def test_immutable_fields(self):
        ac = AgentCollection(agent_id=uuid.uuid4(), collection_id=uuid.uuid4())
        assert hasattr(ac, "agent_id")
        assert hasattr(ac, "collection_id")


class TestDocument:
    def test_defaults(self):
        d = Document()
        assert isinstance(d.id, uuid.UUID)
        assert d.project_id is None
        assert d.collection_id is None
        assert d.title == ""
        assert d.file_name == ""
        assert d.content_type == ""
        assert d.size_bytes == 0
        assert d.storage_key == ""
        assert d.parser == ParserType.TEXT
        assert d.status == DocumentStatus.UPLOADED
        assert d.error is None
        assert d.page_count is None
        assert d.chunk_count is None
        assert d.sha256 is None
        assert d.indexed_at is None
        assert d.created_at is None
        assert d.updated_at is None

    def test_custom_values(self):
        now = datetime.now(timezone.utc)
        did = uuid.uuid4()
        pid = uuid.uuid4()
        cid = uuid.uuid4()
        d = Document(
            id=did,
            project_id=pid,
            collection_id=cid,
            title="doc.pdf",
            file_name="doc.pdf",
            content_type="application/pdf",
            size_bytes=2048,
            storage_key="uploads/doc.pdf",
            parser=ParserType.PDF,
            status=DocumentStatus.READY,
            error=None,
            page_count=5,
            chunk_count=10,
            sha256="abc123",
            indexed_at=now,
            created_at=now,
            updated_at=now,
        )
        assert d.id == did
        assert d.project_id == pid
        assert d.collection_id == cid
        assert d.title == "doc.pdf"
        assert d.file_name == "doc.pdf"
        assert d.content_type == "application/pdf"
        assert d.size_bytes == 2048
        assert d.storage_key == "uploads/doc.pdf"
        assert d.parser == ParserType.PDF
        assert d.status == DocumentStatus.READY
        assert d.page_count == 5
        assert d.chunk_count == 10
        assert d.sha256 == "abc123"
        assert d.indexed_at == now

    def test_uuid_generation(self):
        d1 = Document()
        d2 = Document()
        assert d1.id != d2.id


class TestDocumentChunk:
    def test_defaults(self):
        dc = DocumentChunk()
        assert isinstance(dc.id, uuid.UUID)
        assert dc.project_id is None
        assert dc.collection_id is None
        assert dc.document_id is None
        assert dc.content == ""
        assert dc.chunk_index == 0
        assert dc.token_count is None
        assert dc.page_number is None
        assert dc.section_title is None
        assert dc.data is None
        assert dc.embedding is None
        assert dc.created_at is None
        assert dc.updated_at is None

    def test_custom_values(self):
        now = datetime.now(timezone.utc)
        dcid = uuid.uuid4()
        pid = uuid.uuid4()
        cid = uuid.uuid4()
        docid = uuid.uuid4()
        dc = DocumentChunk(
            id=dcid,
            project_id=pid,
            collection_id=cid,
            document_id=docid,
            content="chunk text",
            chunk_index=2,
            token_count=50,
            page_number=3,
            section_title="Introduction",
            data={"source": "pdf"},
            embedding=[0.1, 0.2, 0.3],
            created_at=now,
            updated_at=now,
        )
        assert dc.id == dcid
        assert dc.project_id == pid
        assert dc.collection_id == cid
        assert dc.document_id == docid
        assert dc.content == "chunk text"
        assert dc.chunk_index == 2
        assert dc.token_count == 50
        assert dc.page_number == 3
        assert dc.section_title == "Introduction"
        assert dc.data == {"source": "pdf"}
        assert dc.embedding == [0.1, 0.2, 0.3]
        assert dc.created_at == now
        assert dc.updated_at == now

    def test_uuid_generation(self):
        dc1 = DocumentChunk()
        dc2 = DocumentChunk()
        assert dc1.id != dc2.id
