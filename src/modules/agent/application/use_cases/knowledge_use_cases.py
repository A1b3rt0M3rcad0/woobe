from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID, uuid4

from modules.agent.application.dtos.knowledge_dtos import *
from modules.agent.domain.entities import AgentCollection, Document, DocumentCollection, KnowledgeVersion
from modules.agent.domain.enums import DocumentStatus, KnowledgeVersionStatus, ParserType
from modules.agent.domain.errors import DocumentNotFoundError
from modules.agent.domain.events import AgentCollectionCreatedV1, AgentDocumentUploadedV1
from modules.agent.domain.ports.file_storage import FileStorage, compute_sha256
from modules.agent.domain.repositories import AgentCollectionRepository, DocumentChunkRepository, DocumentCollectionRepository, DocumentRepository, KnowledgeVersionRepository
from modules.agent.domain.vector_snapshot_entities import VECTOR_SNAPSHOT_READY
from shared.infra.config import Settings
from shared.infra.config.interface.unit_of_work import UnitOfWork
from shared.infra.errors import ConflictError, NotFoundError, ValidationError
from shared.messaging.outbox_writer import OutboxEventWriter


class ReadableUploadFile(Protocol):
    filename: str | None
    content_type: str | None
    async def read(self) -> bytes: ...


_EXTENSION_TO_PARSER = {".txt": ParserType.TEXT, ".md": ParserType.MD, ".pdf": ParserType.PDF}
_CONTENT_TYPES_BY_EXTENSION = {
    ".txt": {"text/plain", "application/octet-stream"},
    ".md": {"text/markdown", "text/plain", "text/x-markdown", "application/octet-stream"},
    ".pdf": {"application/pdf", "application/octet-stream"},
}


def _as_value(value: object) -> object:
    return getattr(value, "value", value)


def _is_deleted_document(document: Document) -> bool:
    return _as_value(document.status) == _as_value(DocumentStatus.DELETED)


def _document_to_upload_output(document: Document) -> UploadDocumentOutput:
    return UploadDocumentOutput(id=document.id, project_id=document.project_id, collection_id=document.collection_id, title=document.title, file_name=document.file_name, content_type=document.content_type, size_bytes=document.size_bytes, storage_key=document.storage_key, parser=document.parser, status=document.status, page_count=document.page_count, chunk_count=document.chunk_count, error=document.error, sha256=document.sha256, indexed_at=document.indexed_at, created_at=document.created_at, updated_at=document.updated_at)


class ListAgentCollectionsUseCase:
    def __init__(self, repo: AgentCollectionRepository) -> None: self._repo = repo
    async def execute(self, agent_id: UUID) -> list[AgentCollectionOutput]:
        return [AgentCollectionOutput(id=l.id, agent_id=l.agent_id, collection_id=l.collection_id, created_at=l.created_at, updated_at=l.updated_at) for l in await self._repo.list_by_agent(agent_id)]


class AttachCollectionUseCase:
    def __init__(self, repo: AgentCollectionRepository) -> None: self._repo = repo
    async def execute(self, input_dto: AttachCollectionInput) -> AttachCollectionOutput:
        if await self._repo.get_by_agent_and_collection(input_dto.agent_id, input_dto.collection_id):
            raise ConflictError("Collection already attached to this agent")
        c = await self._repo.create(AgentCollection(agent_id=input_dto.agent_id, collection_id=input_dto.collection_id))
        return AttachCollectionOutput(id=c.id, agent_id=c.agent_id, collection_id=c.collection_id, created_at=c.created_at, updated_at=c.updated_at)


class DetachCollectionUseCase:
    def __init__(self, repo: AgentCollectionRepository) -> None: self._repo = repo
    async def execute(self, link_id: UUID) -> None: await self._repo.delete(link_id)


class CreateCollectionUseCase:
    def __init__(self, repo: DocumentCollectionRepository, outbox: OutboxEventWriter) -> None:
        self.repo = repo; self._outbox = outbox
    async def execute(self, input_dto: CreateCollectionInput) -> CreateCollectionOutput:
        c = await self.repo.create(DocumentCollection(project_id=input_dto.project_id, name=input_dto.name, description=input_dto.description))
        await self._outbox.write(AgentCollectionCreatedV1.create(collection_id=c.id, project_id=c.project_id, name=c.name))
        return CreateCollectionOutput(id=c.id, project_id=c.project_id, name=c.name, description=c.description, status=c.status, created_at=c.created_at, updated_at=c.updated_at)


class UploadDocumentUseCase:
    def __init__(self, doc_repo: DocumentRepository, collection_repo: DocumentCollectionRepository, outbox: OutboxEventWriter) -> None:
        self.doc_repo = doc_repo; self.collection_repo = collection_repo; self._outbox = outbox
    async def execute(self, input_dto: UploadDocumentInput) -> UploadDocumentOutput:
        await self.collection_repo.get_by_id(input_dto.collection_id)
        d = await self.doc_repo.create(Document(project_id=input_dto.project_id, collection_id=input_dto.collection_id, title=input_dto.title, file_name=input_dto.file_name, content_type=input_dto.content_type, size_bytes=input_dto.size_bytes, storage_key=input_dto.storage_key, parser=input_dto.parser, status=DocumentStatus.UPLOADED))
        await self._outbox.write(AgentDocumentUploadedV1.create(document_id=d.id, collection_id=d.collection_id, project_id=d.project_id, file_name=d.file_name, storage_key=d.storage_key, parser=str(_as_value(d.parser))))
        return _document_to_upload_output(d)


class UploadDocumentFileUseCase:
    def __init__(self, doc_repo: DocumentRepository, collection_repo: DocumentCollectionRepository, outbox: OutboxEventWriter, storage: FileStorage, settings: Settings) -> None:
        self.doc_repo = doc_repo; self.collection_repo = collection_repo; self._outbox = outbox; self._storage = storage; self._settings = settings
    async def execute(self, input_dto: UploadDocumentFileInput, upload: ReadableUploadFile) -> UploadDocumentOutput:
        await self.collection_repo.get_by_id(input_dto.collection_id)
        file_name = self._validate_file_name(upload.filename)
        extension = Path(file_name).suffix.lower()
        parser = self._validate_extension(extension)
        content_type = self._resolve_content_type(file_name, upload.content_type, extension)
        content = await upload.read()
        self._validate_content(content, extension)
        sha256 = compute_sha256(content)
        documents = await self.doc_repo.list_by_collection(input_dto.collection_id)
        if any(d.sha256 == sha256 and not _is_deleted_document(d) for d in documents):
            raise ConflictError("Document already exists in this collection")
        document_id = uuid4()
        stored = await self._storage.save_document(content=content, project_id=input_dto.project_id, collection_id=input_dto.collection_id, document_id=document_id, file_name=file_name, content_type=content_type)
        document = Document(id=document_id, project_id=input_dto.project_id, collection_id=input_dto.collection_id, title=(input_dto.title or "").strip() or Path(stored.file_name).stem, file_name=stored.file_name, content_type=stored.content_type, size_bytes=stored.size_bytes, storage_key=stored.storage_key, parser=parser, status=DocumentStatus.UPLOADED, sha256=sha256)
        try:
            d = await self.doc_repo.create(document)
            await self._outbox.write(AgentDocumentUploadedV1.create(document_id=d.id, collection_id=d.collection_id, project_id=d.project_id, file_name=d.file_name, storage_key=d.storage_key, parser=str(_as_value(d.parser)), payload={"content_type": d.content_type, "size_bytes": d.size_bytes, "sha256": d.sha256, "storage_driver": self._settings.storage_driver}))
        except Exception:
            await self._storage.delete(stored.storage_key)
            raise
        return _document_to_upload_output(d)
    def _validate_file_name(self, file_name: str | None) -> str:
        if not file_name or not file_name.strip(): raise ValidationError("File name is required")
        name = Path(file_name.replace("\\", "/")).name.strip()
        if not name: raise ValidationError("File name is invalid")
        return name
    def _allowed_extensions(self) -> set[str]: return {item.strip().lower() for item in self._settings.upload_allowed_extensions.split(",") if item.strip()}
    def _validate_extension(self, extension: str) -> ParserType:
        if extension not in self._allowed_extensions(): raise ValidationError("Only .txt, .md and .pdf uploads are supported")
        parser = _EXTENSION_TO_PARSER.get(extension)
        if parser is None: raise ValidationError(f"Unsupported document extension: {extension}")
        return parser
    def _resolve_content_type(self, file_name: str, content_type: str | None, extension: str) -> str:
        guessed = mimetypes.guess_type(file_name)[0]
        normalized = (content_type or guessed or "application/octet-stream").split(";", 1)[0].strip().lower()
        if normalized not in _CONTENT_TYPES_BY_EXTENSION.get(extension, set()): raise ValidationError(f"Invalid content type for {extension}: {normalized or 'unknown'}")
        return guessed if normalized == "application/octet-stream" and guessed else normalized
    def _validate_content(self, content: bytes, extension: str) -> None:
        if not content: raise ValidationError("Uploaded file is empty")
        if len(content) > self._settings.upload_max_mb * 1024 * 1024: raise ValidationError(f"Uploaded file exceeds {self._settings.upload_max_mb} MB")
        if extension == ".pdf" and not content.startswith(b"%PDF"): raise ValidationError("Uploaded file is not a valid PDF")
        if extension in {".txt", ".md"}:
            try: content.decode("utf-8")
            except UnicodeDecodeError as exc: raise ValidationError("Text and Markdown uploads must be valid UTF-8") from exc


class DeleteDocumentUseCase:
    def __init__(self, doc_repo: DocumentRepository, chunk_repo: DocumentChunkRepository, storage: FileStorage) -> None:
        self._doc_repo = doc_repo; self._chunk_repo = chunk_repo; self._storage = storage
    async def execute(self, document_id: UUID) -> None:
        d = await self._doc_repo.get_by_id(document_id)
        if _is_deleted_document(d): return
        await self._chunk_repo.delete_by_document(d.id)
        if d.storage_key: await self._storage.delete(d.storage_key)
        d.status = DocumentStatus.DELETED; d.error = None
        await self._doc_repo.update(d)


class SearchChunksUseCase:
    def __init__(self, repo: DocumentChunkRepository) -> None: self.repo = repo
    async def execute(self, input_dto: SearchChunksInput) -> SearchChunksOutput:
        results = await self.repo.search_similar(embedding=input_dto.embedding, collection_id=input_dto.collection_id, limit=input_dto.limit, threshold=input_dto.threshold)
        return SearchChunksOutput(results=[DocumentChunkOutput(id=c.id, content=c.content, chunk_index=c.chunk_index, token_count=c.token_count, page_number=c.page_number, section_title=c.section_title, data=c.data, similarity=s) for c, s in results], total=len(results))


class ListCollectionsUseCase:
    def __init__(self, repo: DocumentCollectionRepository) -> None: self._repo = repo
    async def execute(self, input_dto: ListCollectionsInput) -> list[DocumentCollection]: return [] if not input_dto.project_id else await self._repo.list_by_project(input_dto.project_id)


class GetCollectionUseCase:
    def __init__(self, repo: DocumentCollectionRepository) -> None: self._repo = repo
    async def execute(self, input_dto: GetCollectionInput) -> DocumentCollection: return await self._repo.get_by_id(input_dto.collection_id)


class ListDocumentsUseCase:
    def __init__(self, repo: DocumentRepository, uow: UnitOfWork) -> None: self._repo = repo; self._uow = uow
    async def execute(self, input_dto: ListDocumentsInput) -> list[Document]:
        if input_dto.collection_id: documents = await self._repo.list_by_collection(input_dto.collection_id)
        elif input_dto.project_id: documents = await self._repo.list_by_project(input_dto.project_id)
        else: return []
        return [d for d in documents if not _is_deleted_document(d)]


class GetDocumentUseCase:
    def __init__(self, repo: DocumentRepository) -> None: self._repo = repo
    async def execute(self, input_dto: GetDocumentInput) -> Document:
        d = await self._repo.get_by_id(input_dto.document_id)
        if _is_deleted_document(d): raise DocumentNotFoundError(input_dto.document_id)
        return d


class CreateKnowledgeVersionUseCase:
    def __init__(self, repo: KnowledgeVersionRepository, vector_snapshot_repo: Any | None = None) -> None:
        self._repo = repo
        self._vector_snapshot_repo = vector_snapshot_repo

    async def execute(self, input_dto: CreateKnowledgeVersionInput) -> CreateKnowledgeVersionOutput:
        snapshot_metadata = dict(input_dto.snapshot_metadata or {})
        collection_ids = list(input_dto.collection_ids or [])
        vector_snapshot_id = snapshot_metadata.get("vector_snapshot_id")
        if vector_snapshot_id and self._vector_snapshot_repo is not None:
            snapshot = await self._vector_snapshot_repo.get_by_id(UUID(str(vector_snapshot_id)))
            if snapshot is None or snapshot.project_id != input_dto.project_id:
                raise NotFoundError("Vector snapshot not found")
            if snapshot.status != VECTOR_SNAPSHOT_READY:
                raise ConflictError("Knowledge version requires a READY vector snapshot")
            collection_ids = [snapshot.collection_id]
            snapshot_metadata.update(
                {
                    "vector_snapshot_id": str(snapshot.id),
                    "embedding_provider_model_id": str(snapshot.embedding_provider_model_id),
                    "embedding_provider": snapshot.embedding_provider,
                    "embedding_model": snapshot.embedding_model,
                    "embedding_dimensions": snapshot.embedding_dimensions,
                    "snapshot_hash": snapshot.snapshot_hash,
                    "chunk_count": snapshot.chunk_count,
                    "document_count": snapshot.document_count,
                }
            )
        v = await self._repo.save(KnowledgeVersion(project_id=input_dto.project_id, agent_id=input_dto.agent_id, version=input_dto.version, collection_ids=collection_ids, document_ids=input_dto.document_ids, snapshot_metadata=snapshot_metadata, status=KnowledgeVersionStatus.DRAFT))
        return CreateKnowledgeVersionOutput(id=v.id, project_id=v.project_id, agent_id=v.agent_id, version=v.version, collection_ids=v.collection_ids or [], document_ids=v.document_ids, snapshot_metadata=v.snapshot_metadata, status=v.status, created_at=v.created_at, updated_at=v.updated_at)


class ListKnowledgeVersionsUseCase:
    def __init__(self, repo: KnowledgeVersionRepository) -> None: self._repo = repo
    async def execute(self, agent_id: UUID) -> list[ListKnowledgeVersionsOutput]:
        return [ListKnowledgeVersionsOutput(id=v.id, version=v.version, collection_ids=v.collection_ids or [], status=v.status, created_at=v.created_at) for v in await self._repo.list_by_agent(agent_id)]
