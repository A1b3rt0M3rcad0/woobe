from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from modules.agent.domain.entities import (
    AgentCollection,
    Document,
    DocumentCollection,
    KnowledgeVersion,
)
from modules.agent.domain.enums import DocumentStatus, KnowledgeVersionStatus, ParserType
from modules.agent.domain.ports.file_storage import FileStorage
from modules.agent.domain.repositories import (
    AgentCollectionRepository,
    DocumentChunkRepository,
    DocumentCollectionRepository,
    DocumentRepository,
    KnowledgeVersionRepository,
)
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
from modules.agent.domain.events import AgentCollectionCreatedV1, AgentDocumentUploadedV1
from shared.infra.config import Settings
from shared.infra.config.interface.unit_of_work import UnitOfWork
from shared.infra.errors import ConflictError, ValidationError
from shared.messaging.outbox_writer import OutboxEventWriter


class ReadableUploadFile(Protocol):
    filename: str | None
    content_type: str | None

    async def read(self) -> bytes: ...


_EXTENSION_TO_PARSER: dict[str, ParserType] = {
    ".txt": ParserType.TEXT,
    ".md": ParserType.MD,
    ".pdf": ParserType.PDF,
}

_CONTENT_TYPES_BY_EXTENSION: dict[str, set[str]] = {
    ".txt": {"text/plain", "application/octet-stream"},
    ".md": {"text/markdown", "text/plain", "text/x-markdown", "application/octet-stream"},
    ".pdf": {"application/pdf", "application/octet-stream"},
}


def _as_value(value: object) -> object:
    return getattr(value, "value", value)


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
        sha256=document.sha256,
        indexed_at=document.indexed_at,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


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

    def __init__(
        self,
        repo: AgentCollectionRepository,
    ) -> None:
        self._repo = repo

    async def execute(self, input_dto: AttachCollectionInput) -> AttachCollectionOutput:
        existing = await self._repo.get_by_agent_and_collection(
            input_dto.agent_id, input_dto.collection_id
        )
        if existing:
            raise ConflictError("Collection already attached to this agent")

        link = AgentCollection(
            agent_id=input_dto.agent_id,
            collection_id=input_dto.collection_id,
        )
        created = await self._repo.create(link)
        return AttachCollectionOutput(
            id=created.id,
            agent_id=created.agent_id,
            collection_id=created.collection_id,
            created_at=created.created_at,
            updated_at=created.updated_at,
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

    async def execute(self, input_dto: CreateCollectionInput) -> CreateCollectionOutput:
        collection = DocumentCollection(
            project_id=input_dto.project_id,
            name=input_dto.name,
            description=input_dto.description,
        )
        created = await self.repo.create(collection)

        event = AgentCollectionCreatedV1.create(
            collection_id=created.id,
            project_id=created.project_id,
            name=created.name,
        )
        await self._outbox.write(event)

        return CreateCollectionOutput(
            id=created.id,
            project_id=created.project_id,
            name=created.name,
            description=created.description,
            status=created.status,
            created_at=created.created_at,
            updated_at=created.updated_at,
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

    async def execute(self, input_dto: UploadDocumentInput) -> UploadDocumentOutput:
        await self.collection_repo.get_by_id(input_dto.collection_id)

        document = Document(
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
        created = await self.doc_repo.create(document)

        event = AgentDocumentUploadedV1.create(
            document_id=created.id,
            collection_id=created.collection_id,
            project_id=created.project_id,
            file_name=created.file_name,
            storage_key=created.storage_key,
            parser=str(_as_value(created.parser)),
        )
        await self._outbox.write(event)

        return _document_to_upload_output(created)


class UploadDocumentFileUseCase:
    def __init__(
        self,
        doc_repo: DocumentRepository,
        collection_repo: DocumentCollectionRepository,
        outbox: OutboxEventWriter,
        storage: FileStorage,
        settings: Settings,
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
        content_type = self._resolve_content_type(file_name, upload.content_type, extension)

        content = await upload.read()
        self._validate_content(content, extension)

        document_id = uuid4()
        stored = await self._storage.save_document(
            content=content,
            project_id=input_dto.project_id,
            collection_id=input_dto.collection_id,
            document_id=document_id,
            file_name=file_name,
            content_type=content_type,
        )

        title = (input_dto.title or "").strip() or Path(stored.file_name).stem
        document = Document(
            id=document_id,
            project_id=input_dto.project_id,
            collection_id=input_dto.collection_id,
            title=title,
            file_name=stored.file_name,
            content_type=stored.content_type,
            size_bytes=stored.size_bytes,
            storage_key=stored.storage_key,
            parser=parser,
            status=DocumentStatus.UPLOADED,
            sha256=stored.sha256,
        )

        try:
            created = await self.doc_repo.create(document)
            event = AgentDocumentUploadedV1.create(
                document_id=created.id,
                collection_id=created.collection_id,
                project_id=created.project_id,
                file_name=created.file_name,
                storage_key=created.storage_key,
                parser=str(_as_value(created.parser)),
                payload={
                    "content_type": created.content_type,
                    "size_bytes": created.size_bytes,
                    "sha256": created.sha256,
                    "storage_driver": self._settings.storage_driver,
                },
            )
            await self._outbox.write(event)
        except Exception:
            await self._storage.delete(stored.storage_key)
            raise

        return _document_to_upload_output(created)

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
        normalized = (content_type or guessed or "application/octet-stream").split(";", 1)[0].strip().lower()
        allowed = _CONTENT_TYPES_BY_EXTENSION.get(extension, set())
        if normalized not in allowed:
            raise ValidationError(
                f"Invalid content type for {extension}: {normalized or 'unknown'}"
            )
        if normalized == "application/octet-stream" and guessed:
            return guessed
        return normalized

    def _validate_content(self, content: bytes, extension: str) -> None:
        if not content:
            raise ValidationError("Uploaded file is empty")

        max_bytes = self._settings.upload_max_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise ValidationError(
                f"Uploaded file exceeds {self._settings.upload_max_mb} MB"
            )

        if extension == ".pdf" and not content.startswith(b"%PDF"):
            raise ValidationError("Uploaded file is not a valid PDF")

        if extension in {".txt", ".md"}:
            try:
                content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValidationError("Text and Markdown uploads must be valid UTF-8") from exc


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

    def __init__(
        self,
        repo: DocumentChunkRepository,
    ) -> None:
        self.repo = repo

    async def execute(self, input_dto: SearchChunksInput) -> SearchChunksOutput:
        results = await self.repo.search_similar(
            embedding=input_dto.embedding,
            collection_id=input_dto.collection_id,
            limit=input_dto.limit,
            threshold=input_dto.threshold,
        )
        outputs = []
        for chunk, similarity in results:
            outputs.append(
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
            )
        return SearchChunksOutput(results=outputs, total=len(outputs))


class ListCollectionsUseCase:

    def __init__(self, repo: DocumentCollectionRepository) -> None:
        self._repo = repo

    async def execute(self, input_dto: ListCollectionsInput) -> list:
        if not input_dto.project_id:
            return []
        collections = await self._repo.list_by_project(input_dto.project_id)
        return collections


class GetCollectionUseCase:

    def __init__(self, repo: DocumentCollectionRepository) -> None:
        self._repo = repo

    async def execute(self, input_dto: GetCollectionInput) -> DocumentCollection:
        return await self._repo.get_by_id(input_dto.collection_id)


class ListDocumentsUseCase:

    def __init__(self, repo: DocumentRepository, uow: UnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(self, input_dto: ListDocumentsInput) -> list:
        if input_dto.collection_id:
            documents = await self._repo.list_by_collection(input_dto.collection_id)
            return [document for document in documents if not _is_deleted_document(document)]
        if input_dto.project_id:
            documents = await self._repo.list_by_project(input_dto.project_id)
            return [document for document in documents if not _is_deleted_document(document)]
        return []


class GetDocumentUseCase:

    def __init__(self, repo: DocumentRepository) -> None:
        self._repo = repo

    async def execute(self, input_dto: GetDocumentInput) -> Document:
        document = await self._repo.get_by_id(input_dto.document_id)
        if _is_deleted_document(document):
            from modules.agent.domain.errors import DocumentNotFoundError
            raise DocumentNotFoundError(input_dto.document_id)
        return document


class CreateKnowledgeVersionUseCase:

    def __init__(self, repo: KnowledgeVersionRepository) -> None:
        self._repo = repo

    async def execute(self, input_dto: CreateKnowledgeVersionInput) -> CreateKnowledgeVersionOutput:
        version = KnowledgeVersion(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            version=input_dto.version,
            collection_ids=input_dto.collection_ids,
            document_ids=input_dto.document_ids,
            snapshot_metadata=input_dto.snapshot_metadata,
            status=KnowledgeVersionStatus.DRAFT,
        )
        saved = await self._repo.save(version)
        return CreateKnowledgeVersionOutput(
            id=saved.id, project_id=saved.project_id, agent_id=saved.agent_id,
            version=saved.version, collection_ids=saved.collection_ids or [],
            document_ids=saved.document_ids, snapshot_metadata=saved.snapshot_metadata,
            status=saved.status, created_at=saved.created_at, updated_at=saved.updated_at,
        )


class ListKnowledgeVersionsUseCase:

    def __init__(self, repo: KnowledgeVersionRepository) -> None:
        self._repo = repo

    async def execute(self, agent_id: UUID) -> list[ListKnowledgeVersionsOutput]:
        versions = await self._repo.list_by_agent(agent_id)
        return [ListKnowledgeVersionsOutput(
            id=v.id, version=v.version, collection_ids=v.collection_ids or [],
            status=v.status, created_at=v.created_at,
        ) for v in versions]
