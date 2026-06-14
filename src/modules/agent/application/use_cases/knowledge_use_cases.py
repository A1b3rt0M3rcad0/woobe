from __future__ import annotations
from uuid import UUID

from modules.agent.domain.entities import (
    AgentCollection,
    Document,
    DocumentCollection,
    KnowledgeVersion,
)
from modules.agent.domain.enums import DocumentStatus, KnowledgeVersionStatus
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
    UploadDocumentInput,
    UploadDocumentOutput,
)

from shared.domain.events import OutboxEventWriter
from shared.infra.config.interface.unit_of_work import UnitOfWork


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
            from shared.domain.errors import ConflictError
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

        await self._outbox.write(
            aggregate_type="document_collection",
            aggregate_id=created.id,
            event_type="knowledge.collection.created",
            payload={
                "collection_id": str(created.id),
                "project_id": str(created.project_id),
                "name": created.name,
            },
        )

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

        await self._outbox.write(
            aggregate_type="document",
            aggregate_id=created.id,
            event_type="knowledge.document.uploaded",
            payload={
                "document_id": str(created.id),
                "collection_id": str(created.collection_id),
                "project_id": str(created.project_id),
                "file_name": created.file_name,
                "storage_key": created.storage_key,
                "parser": created.parser,
            },
        )

        return UploadDocumentOutput(
            id=created.id,
            project_id=created.project_id,
            collection_id=created.collection_id,
            title=created.title,
            file_name=created.file_name,
            content_type=created.content_type,
            size_bytes=created.size_bytes,
            storage_key=created.storage_key,
            parser=created.parser,
            status=created.status,
            page_count=created.page_count,
            chunk_count=created.chunk_count,
            error=created.error,
            indexed_at=created.indexed_at,
            created_at=created.created_at,
            updated_at=created.updated_at,
        )


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
            return await self._repo.list_by_collection(input_dto.collection_id)
        if input_dto.project_id:
            return await self._repo.list_by_project(input_dto.project_id)
        return []


class GetDocumentUseCase:

    def __init__(self, repo: DocumentRepository) -> None:
        self._repo = repo

    async def execute(self, input_dto: GetDocumentInput) -> Document:
        return await self._repo.get_by_id(input_dto.document_id)


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
