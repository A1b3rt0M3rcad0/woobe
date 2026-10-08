from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID, uuid4

from modules.agent.application.dtos.knowledge_dtos import (
    AgentCollectionOutput,
    AttachCollectionInput,
    AttachCollectionOutput,
    CreateCollectionInput,
    CreateCollectionOutput,
    CreateKnowledgeVersionInput,
    CreateKnowledgeVersionOutput,
    DocumentChunkOutput,
    GetCollectionInput,
    GetDocumentInput,
    ListCollectionsInput,
    ListDocumentsInput,
    ListKnowledgeVersionsOutput,
    SearchChunksInput,
    SearchChunksOutput,
    UploadDocumentFileInput,
    UploadDocumentInput,
    UploadDocumentOutput,
)
from modules.agent.domain.entities import (
    AgentCollection,
    Document,
    DocumentCollection,
    KnowledgeVersion,
)
from modules.agent.domain.enums import (
    DocumentStatus,
    KnowledgeVersionStatus,
    ParserType,
)
from modules.agent.domain.errors import DocumentNotFoundError
from modules.agent.domain.events import (
    AgentCollectionCreatedV1,
    AgentDocumentUploadedV1,
)
from modules.agent.application.interfaces.file_storage import FileStorage, compute_sha256
from modules.agent.application.interfaces.repositories import (
    AgentCollectionRepository,
    AgentRepository,
    DocumentChunkRepository,
    DocumentCollectionRepository,
    DocumentRepository,
    KnowledgeVersionRepository,
)
from modules.agent.domain.vector_snapshot_entities import VECTOR_SNAPSHOT_READY
from shared.contracts.errors import ConflictError, NotFoundError, ValidationError
from modules.agent.application.interfaces.outbox import OutboxEventWriter


class ReadableUploadFile(Protocol):
    filename: str | None
    content_type: str | None

    async def read(self) -> bytes: ...


class UploadSettings(Protocol):
    storage_driver: str
    upload_allowed_extensions: str
    upload_max_mb: int


_EXTENSION_TO_PARSER = {
    ".txt": ParserType.TEXT,
    ".md": ParserType.MD,
    ".pdf": ParserType.PDF,
}
_CONTENT_TYPES_BY_EXTENSION = {
    ".txt": {"text/plain", "application/octet-stream"},
    ".md": {
        "text/markdown",
        "text/plain",
        "text/x-markdown",
        "application/octet-stream",
    },
    ".pdf": {"application/pdf", "application/octet-stream"},
}


def _as_value(value: object) -> object:
    return getattr(value, "value", value)


def _document_sha256(document: Document) -> str | None:
    return getattr(document, "sha256", None)


def _is_deleted_document(document: Document) -> bool:
    return _as_value(document.status) == _as_value(DocumentStatus.DELETED)


def _document_to_upload_output(document: Document) -> UploadDocumentOutput:
    return UploadDocumentOutput(
        id=document.id,
        project_id=document.project_id,
        collection_id=document.collection_id,
        title=document.title,
        file_name=document.file_name,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        storage_key=document.storage_key,
        parser=document.parser,
        status=document.status,
        page_count=document.page_count,
        chunk_count=document.chunk_count,
        error=document.error,
        sha256=_document_sha256(document),
        indexed_at=document.indexed_at,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _knowledge_version_to_output(
    version: KnowledgeVersion,
) -> CreateKnowledgeVersionOutput:
    return CreateKnowledgeVersionOutput(
        id=version.id,
        project_id=version.project_id,
        agent_id=version.agent_id,
        version=version.version,
        collection_ids=version.collection_ids or [],
        document_ids=version.document_ids,
        snapshot_metadata=version.snapshot_metadata,
        status=version.status,
        created_at=version.created_at,
        updated_at=version.updated_at,
    )


def _next_knowledge_version(existing: list[KnowledgeVersion]) -> str:
    highest = 0
    for version in existing:
        raw = (version.version or "").strip().lower()
        if raw.startswith("v"):
            raw = raw[1:]
        try:
            highest = max(highest, int(raw))
        except ValueError:
            continue
    return f"v{highest + 1}"


class ListAgentCollectionsUseCase:
    def __init__(self, repo: AgentCollectionRepository) -> None:
        self._repo = repo

    async def execute(self, agent_id: UUID) -> list[AgentCollectionOutput]:
        links = await self._repo.list_by_agent(agent_id)
        return [
            AgentCollectionOutput(
                id=link.id,
                agent_id=link.agent_id,
                collection_id=link.collection_id,
                created_at=link.created_at,
                updated_at=link.updated_at,
            )
            for link in links
        ]


class AttachCollectionUseCase:
    def __init__(self, repo: AgentCollectionRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        input_dto: AttachCollectionInput,
    ) -> AttachCollectionOutput:
        existing = await self._repo.get_by_agent_and_collection(
            input_dto.agent_id,
            input_dto.collection_id,
        )
        if existing:
            raise ConflictError("Collection already attached to this agent")

        link = await self._repo.create(
            AgentCollection(
                agent_id=input_dto.agent_id,
                collection_id=input_dto.collection_id,
            )
        )
        return AttachCollectionOutput(
            id=link.id,
            agent_id=link.agent_id,
            collection_id=link.collection_id,
            created_at=link.created_at,
            updated_at=link.updated_at,
        )


class DetachCollectionUseCase:
    def __init__(self, repo: AgentCollectionRepository) -> None:
        self._repo = repo

    async def execute(self, link_id: UUID) -> None:
        await self._repo.delete(link_id)


class CreateCollectionUseCase:
    def __init__(
        self,
        repo: DocumentCollectionRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self.repo = repo
        self._outbox = outbox

    async def execute(
        self,
        input_dto: CreateCollectionInput,
    ) -> CreateCollectionOutput:
        collection = await self.repo.create(
            DocumentCollection(
                project_id=input_dto.project_id,
                name=input_dto.name,
                description=input_dto.description,
            )
        )
        await self._outbox.write(
            AgentCollectionCreatedV1.create(
                collection_id=collection.id,
                project_id=collection.project_id,
                name=collection.name,
            )
        )
        return CreateCollectionOutput(
            id=collection.id,
            project_id=collection.project_id,
            name=collection.name,
            description=collection.description,
            status=collection.status,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        )


class UploadDocumentUseCase:
    def __init__(
        self,
        doc_repo: DocumentRepository,
        collection_repo: DocumentCollectionRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self.doc_repo = doc_repo
        self.collection_repo = collection_repo
        self._outbox = outbox

    async def execute(
        self,
        input_dto: UploadDocumentInput,
    ) -> UploadDocumentOutput:
        collection = await self.collection_repo.get_by_id(input_dto.collection_id)
        if collection is None or collection.project_id != input_dto.project_id:
            raise NotFoundError("Document collection not found")
        document = await self.doc_repo.create(
            Document(
                id=input_dto.document_id or uuid4(),
                sha256=input_dto.sha256,
                project_id=input_dto.project_id,
                collection_id=input_dto.collection_id,
                title=input_dto.title,
                file_name=input_dto.file_name,
                content_type=input_dto.content_type,
                size_bytes=input_dto.size_bytes,
                storage_key=input_dto.storage_key,
                parser=input_dto.parser,
                status=DocumentStatus.UPLOADED,
            )
        )
        await self._outbox.write(
            AgentDocumentUploadedV1.create(
                document_id=document.id,
                collection_id=document.collection_id,
                project_id=document.project_id,
                file_name=document.file_name,
                storage_key=document.storage_key,
                parser=str(_as_value(document.parser)),
            )
        )
        return _document_to_upload_output(document)


class DocumentUploadPolicy:
    def __init__(self, settings: UploadSettings):
        self._settings = settings

    def prepare(self, *, file_name, content_type, content):
        name = self._validate_file_name(file_name)
        extension = Path(name).suffix.lower()
        parser = self._validate_extension(extension)
        media = self._resolve_content_type(name, content_type, extension)
        self._validate_content(content, extension)
        return name, media, parser

    def _validate_file_name(self, file_name: str | None) -> str:
        if not file_name or not file_name.strip():
            raise ValidationError("File name is required")
        name = Path(file_name.replace("\\", "/")).name.strip()
        if not name:
            raise ValidationError("File name is invalid")
        return name

    def _allowed_extensions(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self._settings.upload_allowed_extensions.split(",")
            if item.strip()
        }

    def _validate_extension(self, extension: str) -> ParserType:
        if extension not in self._allowed_extensions():
            raise ValidationError("Only .txt, .md and .pdf uploads are supported")
        parser = _EXTENSION_TO_PARSER.get(extension)
        if parser is None:
            raise ValidationError(f"Unsupported document extension: {extension}")
        return parser

    def _resolve_content_type(
        self,
        file_name: str,
        content_type: str | None,
        extension: str,
    ) -> str:
        guessed = mimetypes.guess_type(file_name)[0]
        normalized = (
            content_type or guessed or "application/octet-stream"
        ).split(";", 1)[0].strip().lower()
        if normalized not in _CONTENT_TYPES_BY_EXTENSION.get(extension, set()):
            raise ValidationError(
                f"Invalid content type for {extension}: {normalized or 'unknown'}"
            )
        if normalized == "application/octet-stream" and guessed:
            return guessed
        return normalized

    def _validate_content(self, content: bytes, extension: str) -> None:
        if not content:
            raise ValidationError("Uploaded file is empty")
        if len(content) > self._settings.upload_max_mb * 1024 * 1024:
            raise ValidationError(
                f"Uploaded file exceeds {self._settings.upload_max_mb} MB"
            )
        if extension == ".pdf" and not content.startswith(b"%PDF"):
            raise ValidationError("Uploaded file is not a valid PDF")
        if extension in {".txt", ".md"}:
            try:
                content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValidationError(
                    "Text and Markdown uploads must be valid UTF-8"
                ) from exc


class UploadDocumentFileUseCase(DocumentUploadPolicy):
    def __init__(
        self,
        doc_repo: DocumentRepository,
        collection_repo: DocumentCollectionRepository,
        outbox: OutboxEventWriter,
        storage: FileStorage,
        settings: UploadSettings,
    ) -> None:
        self.doc_repo = doc_repo
        self.collection_repo = collection_repo
        self._outbox = outbox
        self._storage = storage
        self._settings = settings

    async def execute(
        self,
        input_dto: UploadDocumentFileInput,
        upload: ReadableUploadFile,
    ) -> UploadDocumentOutput:
        await self.collection_repo.get_by_id(input_dto.collection_id)
        file_name = self._validate_file_name(upload.filename)
        extension = Path(file_name).suffix.lower()
        parser = self._validate_extension(extension)
        content_type = self._resolve_content_type(
            file_name,
            upload.content_type,
            extension,
        )
        content = await upload.read()
        self._validate_content(content, extension)
        sha256 = compute_sha256(content)

        documents = await self.doc_repo.list_by_collection(input_dto.collection_id)
        if any(
            _document_sha256(document) == sha256 and not _is_deleted_document(document)
            for document in documents
        ):
            raise ConflictError("Document already exists in this collection")

        document_id = uuid4()
        stored = await self._storage.save_document(
            content=content,
            project_id=input_dto.project_id,
            collection_id=input_dto.collection_id,
            document_id=document_id,
            file_name=file_name,
            content_type=content_type,
        )
        document = Document(
            id=document_id,
            project_id=input_dto.project_id,
            collection_id=input_dto.collection_id,
            title=(input_dto.title or "").strip() or Path(stored.file_name).stem,
            file_name=stored.file_name,
            content_type=stored.content_type,
            size_bytes=stored.size_bytes,
            storage_key=stored.storage_key,
            parser=parser,
            status=DocumentStatus.UPLOADED,
            sha256=sha256,
        )
        try:
            saved = await self.doc_repo.create(document)
            await self._outbox.write(
                AgentDocumentUploadedV1.create(
                    document_id=saved.id,
                    collection_id=saved.collection_id,
                    project_id=saved.project_id,
                    file_name=saved.file_name,
                    storage_key=saved.storage_key,
                    parser=str(_as_value(saved.parser)),
                    payload={
                        "content_type": saved.content_type,
                        "size_bytes": saved.size_bytes,
                        "sha256": _document_sha256(saved),
                        "storage_driver": self._settings.storage_driver,
                    },
                )
            )
        except Exception:
            await self._storage.delete(stored.storage_key)
            raise
        return _document_to_upload_output(saved)



class DeleteDocumentUseCase:
    def __init__(
        self,
        doc_repo: DocumentRepository,
        chunk_repo: DocumentChunkRepository,
        storage: FileStorage,
    ) -> None:
        self._doc_repo = doc_repo
        self._chunk_repo = chunk_repo
        self._storage = storage

    async def execute(self, document_id: UUID) -> None:
        document = await self._doc_repo.get_by_id(document_id)
        if _is_deleted_document(document):
            return
        await self._chunk_repo.delete_by_document(document.id)
        if document.storage_key:
            await self._storage.delete(document.storage_key)
        document.status = DocumentStatus.DELETED
        document.error = None
        await self._doc_repo.update(document)


class SearchChunksUseCase:
    def __init__(self, repo: DocumentChunkRepository) -> None:
        self.repo = repo

    async def execute(self, input_dto: SearchChunksInput) -> SearchChunksOutput:
        results = await self.repo.search_similar(
            embedding=input_dto.embedding,
            collection_id=input_dto.collection_id,
            limit=input_dto.limit,
            threshold=input_dto.threshold,
        )
        return SearchChunksOutput(
            results=[
                DocumentChunkOutput(
                    id=chunk.id,
                    content=chunk.content,
                    chunk_index=chunk.chunk_index,
                    token_count=chunk.token_count,
                    page_number=chunk.page_number,
                    section_title=chunk.section_title,
                    data=chunk.data,
                    similarity=similarity,
                )
                for chunk, similarity in results
            ],
            total=len(results),
        )


class ListCollectionsUseCase:
    def __init__(self, repo: DocumentCollectionRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        input_dto: ListCollectionsInput,
    ) -> list[DocumentCollection]:
        if not input_dto.project_id:
            return []
        return await self._repo.list_by_project(input_dto.project_id)


class GetCollectionUseCase:
    def __init__(self, repo: DocumentCollectionRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        input_dto: GetCollectionInput,
    ) -> DocumentCollection:
        return await self._repo.get_by_id(input_dto.collection_id)


class ListDocumentsUseCase:
    def __init__(self, repo: DocumentRepository, uow: Any) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(self, input_dto: ListDocumentsInput) -> list[Document]:
        if input_dto.collection_id:
            documents = await self._repo.list_by_collection(input_dto.collection_id)
        elif input_dto.project_id:
            documents = await self._repo.list_by_project(input_dto.project_id)
        else:
            return []
        return [
            document
            for document in documents
            if not _is_deleted_document(document)
        ]


class GetDocumentUseCase:
    def __init__(self, repo: DocumentRepository) -> None:
        self._repo = repo

    async def execute(self, input_dto: GetDocumentInput) -> Document:
        document = await self._repo.get_by_id(input_dto.document_id)
        if _is_deleted_document(document):
            raise DocumentNotFoundError(input_dto.document_id)
        return document


class CreateKnowledgeVersionUseCase:
    def __init__(
        self,
        repo: KnowledgeVersionRepository,
        vector_snapshot_repo: Any | None = None,
        agent_repo: AgentRepository | None = None,
    ) -> None:
        self._repo = repo
        self._vector_snapshot_repo = vector_snapshot_repo
        self._agent_repo = agent_repo

    async def execute(
        self,
        input_dto: CreateKnowledgeVersionInput,
    ) -> CreateKnowledgeVersionOutput:
        if self._agent_repo is not None:
            agent = await self._agent_repo.get_by_id(input_dto.agent_id)
            if agent is None or agent.project_id != input_dto.project_id:
                raise NotFoundError("Agent not found")

        snapshot_metadata = dict(input_dto.snapshot_metadata or {})
        collection_ids = list(input_dto.collection_ids or [])
        vector_snapshot_id = snapshot_metadata.get("vector_snapshot_id")
        existing_versions = await self._repo.list_by_agent(input_dto.agent_id)

        if vector_snapshot_id and self._vector_snapshot_repo is not None:
            snapshot_id = UUID(str(vector_snapshot_id))
            snapshot = await self._vector_snapshot_repo.get_by_id(snapshot_id)
            if snapshot is None or snapshot.project_id != input_dto.project_id:
                raise NotFoundError("Vector snapshot not found")
            if snapshot.status != VECTOR_SNAPSHOT_READY:
                raise ConflictError(
                    "Knowledge version requires a READY vector snapshot"
                )

            for existing in existing_versions:
                existing_metadata = existing.snapshot_metadata or {}
                same_snapshot = str(
                    existing_metadata.get("vector_snapshot_id") or ""
                ) == str(snapshot.id)
                is_archived = _as_value(existing.status) == _as_value(
                    KnowledgeVersionStatus.ARCHIVED
                )
                if same_snapshot and not is_archived:
                    return _knowledge_version_to_output(existing)

            collection_ids = [snapshot.collection_id]
            snapshot_metadata.update(
                {
                    "vector_snapshot_id": str(snapshot.id),
                    "vector_snapshot_version": snapshot.version,
                    "embedding_provider_model_id": str(
                        snapshot.embedding_provider_model_id
                    ),
                    "embedding_provider": snapshot.embedding_provider,
                    "embedding_model": snapshot.embedding_model,
                    "embedding_dimensions": snapshot.embedding_dimensions,
                    "snapshot_hash": snapshot.snapshot_hash,
                    "chunk_count": snapshot.chunk_count,
                    "document_count": snapshot.document_count,
                }
            )

        version = input_dto.version or _next_knowledge_version(existing_versions)
        duplicate = await self._repo.get_by_version(input_dto.agent_id, version)
        if duplicate is not None:
            raise ConflictError(
                f"Knowledge version {version} already exists for this agent"
            )

        saved = await self._repo.save(
            KnowledgeVersion(
                project_id=input_dto.project_id,
                agent_id=input_dto.agent_id,
                version=version,
                collection_ids=collection_ids,
                document_ids=input_dto.document_ids,
                snapshot_metadata=snapshot_metadata,
                status=KnowledgeVersionStatus.DRAFT,
            )
        )
        return _knowledge_version_to_output(saved)


class ListKnowledgeVersionsUseCase:
    def __init__(self, repo: KnowledgeVersionRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        agent_id: UUID,
    ) -> list[ListKnowledgeVersionsOutput]:
        versions = await self._repo.list_by_agent(agent_id)
        return [
            ListKnowledgeVersionsOutput(
                id=version.id,
                project_id=version.project_id,
                agent_id=version.agent_id,
                version=version.version,
                collection_ids=version.collection_ids or [],
                document_ids=version.document_ids,
                snapshot_metadata=version.snapshot_metadata,
                status=version.status,
                created_at=version.created_at,
                updated_at=version.updated_at,
            )
            for version in versions
        ]
