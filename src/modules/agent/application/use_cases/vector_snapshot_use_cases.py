from __future__ import annotations

from typing import Any
from uuid import UUID

from modules.agent.application.dtos.vector_snapshot_dtos import (
    CreateVectorSnapshotInput,
    GetVectorSnapshotInput,
    ListVectorSnapshotsInput,
    SearchVectorSnapshotChunksInput,
    VectorSnapshotOutput,
)
from modules.agent.application.services.rag.chunker import RecursiveTextChunker
from modules.agent.application.services.rag.document_parser import DocumentParser
from modules.agent.application.services.rag.snapshot_hasher import (
    compute_content_hash,
    compute_snapshot_hash,
)
from modules.agent.domain.enums import CredentialStatus, DocumentStatus, ProviderModelStatus
from modules.agent.domain.ports.embedding_factory import EmbeddingFactory
from modules.agent.domain.repositories import (
    DocumentCollectionRepository,
    DocumentRepository,
    ProviderCredentialRepository,
)
from modules.agent.domain.vector_snapshot_entities import (
    VECTOR_SNAPSHOT_BUILDING,
    VECTOR_SNAPSHOT_READY,
    VectorSnapshot,
    VectorSnapshotChunk,
    VectorSnapshotDocument,
)
from shared.infra.config import Settings
from shared.infra.crypto import decrypt_secret
from shared.infra.errors import ConflictError, NotFoundError, ValidationError
from shared.infra.time import utc_now


def _value(value: object) -> str:
    return str(getattr(value, "value", value))


def _snapshot_to_output(snapshot: VectorSnapshot) -> VectorSnapshotOutput:
    return VectorSnapshotOutput(
        id=snapshot.id,
        project_id=snapshot.project_id,
        collection_id=snapshot.collection_id,
        version=snapshot.version,
        description=snapshot.description,
        status=snapshot.status,
        embedding_provider_model_id=snapshot.embedding_provider_model_id,
        embedding_provider=snapshot.embedding_provider,
        embedding_model=snapshot.embedding_model,
        embedding_dimensions=snapshot.embedding_dimensions,
        chunk_size=snapshot.chunk_size,
        chunk_overlap=snapshot.chunk_overlap,
        chunking_strategy=snapshot.chunking_strategy,
        parser_config=snapshot.parser_config,
        snapshot_hash=snapshot.snapshot_hash,
        document_count=snapshot.document_count,
        chunk_count=snapshot.chunk_count,
        error_message=snapshot.error_message,
        created_by=snapshot.created_by,
        started_at=snapshot.started_at,
        completed_at=snapshot.completed_at,
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )


class CreateVectorSnapshotUseCase:
    def __init__(
        self,
        *,
        snapshot_repo: Any,
        collection_repo: DocumentCollectionRepository,
        document_repo: DocumentRepository,
        provider_model_repo: Any,
        credential_repo: ProviderCredentialRepository,
    ) -> None:
        self._snapshot_repo = snapshot_repo
        self._collection_repo = collection_repo
        self._document_repo = document_repo
        self._provider_model_repo = provider_model_repo
        self._credential_repo = credential_repo

    async def execute(self, input_dto: CreateVectorSnapshotInput) -> VectorSnapshotOutput:
        if input_dto.chunk_overlap >= input_dto.chunk_size:
            raise ValidationError("chunk_overlap must be lower than chunk_size")

        collection = await self._collection_repo.get_by_id(input_dto.collection_id)
        if collection.project_id != input_dto.project_id:
            raise NotFoundError("Document collection not found")

        existing = await self._snapshot_repo.get_by_collection_version(
            input_dto.project_id,
            input_dto.collection_id,
            input_dto.version,
        )
        if existing is not None:
            raise ConflictError("Vector snapshot version already exists for this collection")

        documents = await self._document_repo.list_by_collection(input_dto.collection_id)
        active_documents = [
            document
            for document in documents
            if _value(document.status) != _value(DocumentStatus.DELETED)
        ]
        if not active_documents:
            raise ConflictError("Collection has no active documents to snapshot")

        provider_model = await self._provider_model_repo.get_by_id(input_dto.embedding_provider_model_id)
        if provider_model is None or provider_model.project_id != input_dto.project_id:
            raise NotFoundError("Embedding provider model not found")
        if _value(provider_model.status) != _value(ProviderModelStatus.active):
            raise ConflictError("Embedding provider model must be active")

        metadata = provider_model.metadata or {}
        capability = str(metadata.get("capability") or metadata.get("type") or "").lower()
        if capability not in {"embedding", "embeddings"} and "embed" not in provider_model.model.lower():
            raise ConflictError("Provider model must be configured as an embedding model")

        dimensions = int(metadata.get("dimensions") or 1536)
        if dimensions != 1536:
            raise ConflictError("Only 1536-dimensional embeddings are supported in the MVP")

        credential = await self._credential_repo.get_by_id(provider_model.provider_credential_id)
        if credential is None or credential.project_id != input_dto.project_id:
            raise NotFoundError("Embedding provider credential not found")
        if _value(credential.status) != _value(CredentialStatus.active):
            raise ConflictError("Embedding provider credential must be active")

        snapshot = VectorSnapshot(
            project_id=input_dto.project_id,
            collection_id=input_dto.collection_id,
            version=input_dto.version,
            description=input_dto.description,
            embedding_provider_model_id=provider_model.id,
            embedding_provider=_value(credential.provider),
            embedding_model=provider_model.model,
            embedding_dimensions=dimensions,
            chunk_size=input_dto.chunk_size,
            chunk_overlap=input_dto.chunk_overlap,
            chunking_strategy=input_dto.chunking_strategy,
            parser_config=input_dto.parser_config,
            created_by=input_dto.created_by,
        )
        created = await self._snapshot_repo.create(snapshot)
        return _snapshot_to_output(created)


class ListVectorSnapshotsUseCase:
    def __init__(self, snapshot_repo: Any) -> None:
        self._snapshot_repo = snapshot_repo

    async def execute(self, input_dto: ListVectorSnapshotsInput) -> list[VectorSnapshotOutput]:
        snapshots = await self._snapshot_repo.list_by_collection(
            input_dto.project_id,
            input_dto.collection_id,
        )
        return [_snapshot_to_output(snapshot) for snapshot in snapshots]


class GetVectorSnapshotUseCase:
    def __init__(self, snapshot_repo: Any) -> None:
        self._snapshot_repo = snapshot_repo

    async def execute(self, input_dto: GetVectorSnapshotInput) -> VectorSnapshotOutput:
        snapshot = await self._snapshot_repo.get_by_id(input_dto.snapshot_id)
        if snapshot is None:
            raise NotFoundError("Vector snapshot not found")
        if input_dto.project_id and snapshot.project_id != input_dto.project_id:
            raise NotFoundError("Vector snapshot not found")
        return _snapshot_to_output(snapshot)


class BuildVectorSnapshotUseCase:
    def __init__(
        self,
        *,
        snapshot_repo: Any,
        document_repo: DocumentRepository,
        provider_model_repo: Any,
        credential_repo: ProviderCredentialRepository,
        storage: Any,
        embedding_factory: EmbeddingFactory,
        settings: Settings | None = None,
        parser: DocumentParser | None = None,
        chunker: RecursiveTextChunker | None = None,
    ) -> None:
        self._snapshot_repo = snapshot_repo
        self._document_repo = document_repo
        self._provider_model_repo = provider_model_repo
        self._credential_repo = credential_repo
        self._storage = storage
        self._embedding_factory = embedding_factory
        self._settings = settings or Settings()
        self._parser = parser or DocumentParser()
        self._chunker = chunker or RecursiveTextChunker()

    async def execute(self, snapshot_id: UUID) -> VectorSnapshotOutput:
        snapshot = await self._snapshot_repo.get_by_id(snapshot_id)
        if snapshot is None:
            raise NotFoundError("Vector snapshot not found")
        if snapshot.status != VECTOR_SNAPSHOT_BUILDING:
            raise ConflictError("Only BUILDING vector snapshots can be processed")

        await self._snapshot_repo.mark_started(snapshot.id)
        try:
            output = await self._build(snapshot)
            return output
        except Exception as exc:
            await self._snapshot_repo.mark_failed(snapshot.id, str(exc))
            raise

    async def _build(self, snapshot: VectorSnapshot) -> VectorSnapshotOutput:
        provider_model = await self._provider_model_repo.get_by_id(snapshot.embedding_provider_model_id)
        if provider_model is None:
            raise NotFoundError("Embedding provider model not found")
        credential = await self._credential_repo.get_by_id(provider_model.provider_credential_id)
        if credential is None:
            raise NotFoundError("Embedding provider credential not found")

        api_key = decrypt_secret(credential.encrypted_secret, self._settings.encryption_key)
        metadata = provider_model.metadata or {}
        base_url = metadata.get("base_url") or (credential.metadata or {}).get("base_url")
        embedding_client = self._embedding_factory.create_embedding_client(
            provider=snapshot.embedding_provider,
            model=snapshot.embedding_model,
            api_key=api_key,
            base_url=base_url,
            dimensions=snapshot.embedding_dimensions,
        )

        documents = await self._document_repo.list_by_collection(snapshot.collection_id)
        active_documents = [
            document
            for document in documents
            if _value(document.status) != _value(DocumentStatus.DELETED)
        ]
        if not active_documents:
            raise ConflictError("Collection has no active documents to snapshot")

        snapshot_documents: list[VectorSnapshotDocument] = []
        snapshot_chunks: list[VectorSnapshotChunk] = []
        hash_documents: list[dict[str, Any]] = []

        for document in active_documents:
            if not document.storage_key:
                raise ConflictError(f"Document has no storage key: {document.id}")
            raw = await self._storage.read_document(document.storage_key)
            parsed = self._parser.parse(content=raw, parser=document.parser, file_name=document.file_name)
            text_chunks = self._chunker.chunk(
                parsed.text,
                chunk_size=snapshot.chunk_size,
                chunk_overlap=snapshot.chunk_overlap,
            )
            if not text_chunks:
                continue

            texts = [chunk.content for chunk in text_chunks]
            embeddings = await embedding_client.aembed_documents(texts)
            if len(embeddings) != len(text_chunks):
                raise ValidationError("Embedding provider returned an unexpected batch size")

            for chunk, embedding in zip(text_chunks, embeddings, strict=True):
                if len(embedding) != snapshot.embedding_dimensions:
                    raise ConflictError("Embedding provider returned incompatible vector dimensions")
                snapshot_chunks.append(
                    VectorSnapshotChunk(
                        vector_snapshot_id=snapshot.id,
                        project_id=snapshot.project_id,
                        collection_id=snapshot.collection_id,
                        document_id=document.id,
                        content=chunk.content,
                        content_hash=compute_content_hash(chunk.content),
                        chunk_index=chunk.chunk_index,
                        token_count=chunk.token_count,
                        page_number=chunk.page_number,
                        section_title=chunk.section_title,
                        data={"source": "vector_snapshot_build"},
                        embedding=embedding,
                    )
                )

            snapshot_documents.append(
                VectorSnapshotDocument(
                    vector_snapshot_id=snapshot.id,
                    document_id=document.id,
                    document_sha256=document.sha256,
                    document_title=document.title,
                    file_name=document.file_name,
                    parser=_value(document.parser),
                    status_at_build=_value(document.status),
                    chunk_count=len(text_chunks),
                )
            )
            hash_documents.append(
                {
                    "document_id": str(document.id),
                    "sha256": document.sha256,
                    "file_name": document.file_name,
                    "chunk_count": len(text_chunks),
                }
            )
            document.status = DocumentStatus.READY
            document.chunk_count = len(text_chunks)
            document.page_count = parsed.page_count
            document.indexed_at = utc_now()
            await self._document_repo.update(document)

        if not snapshot_chunks:
            raise ConflictError("Vector snapshot build produced no chunks")

        await self._snapshot_repo.add_snapshot_documents(snapshot_documents)
        await self._snapshot_repo.add_snapshot_chunks(snapshot_chunks)
        snapshot_hash = compute_snapshot_hash(
            documents=hash_documents,
            parameters={
                "embedding_provider_model_id": str(snapshot.embedding_provider_model_id),
                "embedding_provider": snapshot.embedding_provider,
                "embedding_model": snapshot.embedding_model,
                "embedding_dimensions": snapshot.embedding_dimensions,
                "chunk_size": snapshot.chunk_size,
                "chunk_overlap": snapshot.chunk_overlap,
                "chunking_strategy": snapshot.chunking_strategy,
                "parser_config": snapshot.parser_config or {},
            },
        )
        ready = await self._snapshot_repo.mark_ready(
            snapshot.id,
            snapshot_hash=snapshot_hash,
            document_count=len(snapshot_documents),
            chunk_count=len(snapshot_chunks),
        )
        if ready is None:
            raise NotFoundError("Vector snapshot not found")
        return _snapshot_to_output(ready)


class SearchVectorSnapshotChunksUseCase:
    def __init__(self, snapshot_repo: Any) -> None:
        self._snapshot_repo = snapshot_repo

    async def execute(self, input_dto: SearchVectorSnapshotChunksInput):
        snapshot = await self._snapshot_repo.get_by_id(input_dto.vector_snapshot_id)
        if snapshot is None:
            raise NotFoundError("Vector snapshot not found")
        if snapshot.status != VECTOR_SNAPSHOT_READY:
            raise ConflictError("Vector snapshot must be READY before search")
        return await self._snapshot_repo.search_similar(
            vector_snapshot_id=input_dto.vector_snapshot_id,
            embedding=input_dto.embedding,
            limit=input_dto.limit,
            threshold=input_dto.threshold,
        )
