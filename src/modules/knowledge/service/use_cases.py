from __future__ import annotations

from modules.knowledge.domain.entities import (
    AgentCollection,
    Document,
    DocumentCollection,
)
from modules.knowledge.domain.enums import DocumentStatus
from modules.knowledge.domain.repositories import (
    AgentCollectionRepository,
    DocumentChunkRepository,
    DocumentCollectionRepository,
    DocumentRepository,
)
from modules.knowledge.infra.models import OutboxEventModel
from modules.knowledge.service.dtos import (
    AgentCollectionOutput,
    AttachCollectionInput,
    AttachCollectionOutput,
    CreateCollectionInput,
    CreateCollectionOutput,
    DocumentChunkOutput,
    SearchChunksInput,
    SearchChunksOutput,
    UploadDocumentInput,
    UploadDocumentOutput,
)
from sqlalchemy.ext.asyncio import AsyncSession


class ListAgentCollectionsUseCase:

    def __init__(self, repo: AgentCollectionRepository) -> None:
        self._repo = repo

    async def execute(self, agent_id: UUID) -> list[AgentCollectionOutput]:
        links = await self._repo.list_by_agent(agent_id)
        return [
            AgentCollectionOutput(
                id=l.id,
                agent_id=l.agent_id,
                collection_id=l.collection_id,
                created_at=l.created_at,
                updated_at=l.updated_at,
            )
            for l in links
        ]


class AttachCollectionUseCase:

    def __init__(
        self,
        session: AsyncSession,
        repo: AgentCollectionRepository,
    ) -> None:
        self.session = session
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
        session: AsyncSession,
        repo: DocumentCollectionRepository,
    ) -> None:
        self.session = session
        self.repo = repo

    async def execute(self, input_dto: CreateCollectionInput) -> CreateCollectionOutput:
        collection = DocumentCollection(
            project_id=input_dto.project_id,
            name=input_dto.name,
            description=input_dto.description,
        )
        created = await self.repo.create(collection)

        event = OutboxEventModel(
            aggregate_type="document_collection",
            aggregate_id=created.id,
            event_type="knowledge.collection.created",
            payload={
                "collection_id": str(created.id),
                "project_id": str(created.project_id),
                "name": created.name,
            },
        )
        self.session.add(event)

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
        session: AsyncSession,
        doc_repo: DocumentRepository,
        collection_repo: DocumentCollectionRepository,
    ) -> None:
        self.session = session
        self.doc_repo = doc_repo
        self.collection_repo = collection_repo

    async def execute(self, input_dto: UploadDocumentInput) -> UploadDocumentOutput:
        collection = await self.collection_repo.get_by_id(input_dto.collection_id)

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

        event = OutboxEventModel(
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
        self.session.add(event)

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

