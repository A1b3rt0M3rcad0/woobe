from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from modules.agent.application.dtos.rag_config_dtos import (
    RAGBuildConfig,
    RAGChunkingConfig,
    RAGParserConfig,
)
from modules.agent.application.dtos.vector_snapshot_dtos import (
    CollectionOverviewDocumentsOutput,
    CollectionOverviewOutput,
    CollectionOverviewProcessingOutput,
    CollectionOverviewTechnologyOutput,
    CreateVectorSnapshotInput,
    GetCollectionOverviewInput,
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
from modules.agent.domain.enums import (
    CredentialStatus,
    DocumentStatus,
    ProviderModelStatus,
)
from modules.agent.domain.model_spec import ModelSpec, ModelOperations
from modules.agent.application.interfaces.embedding_factory import EmbeddingFactory
from modules.agent.application.interfaces.repositories import (
    DocumentCollectionRepository,
    DocumentRepository,
    ProviderCredentialRepository,
)
from modules.agent.domain.vector_snapshot_entities import (
    VECTOR_SNAPSHOT_BUILDING,
    VECTOR_SNAPSHOT_FAILED,
    VECTOR_SNAPSHOT_READY,
    VECTOR_SNAPSHOT_STAGE_CHUNKING,
    VECTOR_SNAPSHOT_STAGE_EMBEDDING,
    VECTOR_SNAPSHOT_STAGE_PARSING,
    VECTOR_SNAPSHOT_STAGE_WRITING,
    VectorSnapshot,
    VectorSnapshotChunk,
    VectorSnapshotDocument,
)
from shared.security.crypto import decrypt_secret
from shared.contracts.errors import ConflictError, NotFoundError, ValidationError
from shared.contracts.time import utc_now

EMBEDDING_BATCH_SIZE = 100


def _value(value: object) -> str:
    return str(getattr(value, "value", value))


def _document_sha256(document: object) -> str | None:
    value = getattr(document, "sha256", None)
    return str(value) if value else None


def _json_hash(value: dict[str, Any]) -> str:
    serialized = json.dumps(
        value,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return compute_content_hash(serialized)


def _snapshot_to_output(snapshot: VectorSnapshot) -> VectorSnapshotOutput:
    return VectorSnapshotOutput(
        id=snapshot.id,
        project_id=snapshot.project_id,
        collection_id=snapshot.collection_id,
        version=snapshot.version,
        description=snapshot.description,
        status=snapshot.status,
        build_stage=snapshot.build_stage,
        embedding_provider_model_id=snapshot.embedding_provider_model_id,
        embedding_provider=snapshot.embedding_provider,
        embedding_model=snapshot.embedding_model,
        embedding_dimensions=snapshot.embedding_dimensions,
        chunk_size=snapshot.chunk_size,
        chunk_overlap=snapshot.chunk_overlap,
        chunking_strategy=snapshot.chunking_strategy,
        parser_config=snapshot.parser_config,
        build_config=snapshot.build_config,
        snapshot_hash=snapshot.snapshot_hash,
        build_config_hash=snapshot.build_config_hash,
        document_count=snapshot.document_count,
        chunk_count=snapshot.chunk_count,
        vector_count=snapshot.vector_count,
        total_document_count=snapshot.total_document_count,
        processed_document_count=snapshot.processed_document_count,
        total_chunk_count=snapshot.total_chunk_count,
        processed_chunk_count=snapshot.processed_chunk_count,
        embedded_chunk_count=snapshot.embedded_chunk_count,
        current_document_id=snapshot.current_document_id,
        error_message=snapshot.error_message,
        created_by=snapshot.created_by,
        started_at=snapshot.started_at,
        completed_at=snapshot.completed_at,
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )


def _dict_value(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalize_build_config(
    input_dto: CreateVectorSnapshotInput,
    *,
    embedding: dict[str, Any],
) -> dict[str, Any]:
    raw = input_dto.build_config or {}
    raw_chunking = _dict_value(raw.get("chunking"))
    raw_parser = _dict_value(raw.get("parser"))

    chunking_payload = {
        **raw_chunking,
        "strategy": raw_chunking.get("strategy")
        or input_dto.chunking_strategy
        or "recursive_text",
        "chunk_size": raw_chunking.get("chunk_size")
        or raw_chunking.get("size")
        or input_dto.chunk_size,
        "chunk_overlap": raw_chunking.get("chunk_overlap")
        or raw_chunking.get("overlap")
        or input_dto.chunk_overlap,
        "min_chunk_size": raw_chunking.get("min_chunk_size")
        or raw_chunking.get("min_chars")
        or 100,
    }
    parser_payload = input_dto.parser_config or raw_parser or {}

    build = RAGBuildConfig(
        parser=RAGParserConfig.model_validate(parser_payload),
        chunking=RAGChunkingConfig.model_validate(chunking_payload),
    ).model_dump()
    build["embedding"] = embedding
    return build


def _snapshot_chunking_config(snapshot: VectorSnapshot) -> RAGChunkingConfig:
    build = snapshot.build_config or {}
    raw = _dict_value(build.get("chunking"))
    payload = {
        **raw,
        "strategy": raw.get("strategy") or snapshot.chunking_strategy,
        "chunk_size": raw.get("chunk_size") or snapshot.chunk_size,
        "chunk_overlap": raw.get("chunk_overlap") or snapshot.chunk_overlap,
        "min_chunk_size": raw.get("min_chunk_size") or raw.get("min_chars") or 100,
    }
    return RAGChunkingConfig.model_validate(payload)


def _snapshot_parser_config(snapshot: VectorSnapshot) -> RAGParserConfig:
    build = snapshot.build_config or {}
    raw = snapshot.parser_config or _dict_value(build.get("parser"))
    return RAGParserConfig.model_validate(raw or {})


def _next_version(snapshots: list[VectorSnapshot]) -> str:
    highest = 0
    for snapshot in snapshots:
        raw = snapshot.version.strip().lower().removeprefix("v")
        if raw.isdigit():
            highest = max(highest, int(raw))
    return f"v{highest + 1}"


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

    async def execute(
        self,
        input_dto: CreateVectorSnapshotInput,
    ) -> VectorSnapshotOutput:
        collection = await self._collection_repo.get_by_id(input_dto.collection_id)
        if collection is None or collection.project_id != input_dto.project_id:
            raise NotFoundError("Document collection not found")

        building = await self._snapshot_repo.get_active_building_by_collection(
            input_dto.project_id,
            input_dto.collection_id,
        )
        if building is not None:
            raise ConflictError(
                "A vector snapshot is already being built for this collection"
            )

        documents = await self._document_repo.list_by_collection(
            input_dto.collection_id
        )
        active_documents = [
            document
            for document in documents
            if _value(document.status) != _value(DocumentStatus.DELETED)
        ]
        if input_dto.document_ids is not None:
            selected = set(input_dto.document_ids)
            if len(selected) != len(input_dto.document_ids):
                raise ConflictError("Vector snapshot document selection must be unique")
            active_documents = [document for document in active_documents if document.id in selected]
            if {document.id for document in active_documents} != selected:
                raise NotFoundError("Selected snapshot document is unavailable in this Collection")
        if not active_documents:
            raise ConflictError("Collection has no active documents to snapshot")

        provider_model = await self._provider_model_repo.get_by_id(
            input_dto.embedding_provider_model_id
        )
        if provider_model is None or provider_model.project_id != input_dto.project_id:
            raise NotFoundError("Embedding provider model not found")
        if _value(provider_model.status) != _value(ProviderModelStatus.active):
            raise ConflictError("Embedding provider model must be active")

        metadata = provider_model.metadata or {}
        capability = str(
            metadata.get("capability") or metadata.get("type") or ""
        ).lower()
        normalized_spec = ModelSpec.from_dict(provider_model.spec) if getattr(provider_model, "spec", None) else None
        is_embedding = (ModelOperations.EMBEDDING_CREATE in normalized_spec.operations
                        if normalized_spec else capability in {"embedding", "embeddings"} or "embed" in provider_model.model.lower())
        if not is_embedding:
            raise ConflictError(
                "Provider model must be configured as an embedding model"
            )

        dimensions = int((normalized_spec.metadata.get("dimensions") if normalized_spec else None) or metadata.get("dimensions") or 1536)
        if dimensions != 1536:
            raise ConflictError(
                "Only 1536-dimensional embeddings are supported in the MVP"
            )

        credential = await self._credential_repo.get_by_id(
            provider_model.provider_credential_id
        )
        if credential is None or credential.project_id != input_dto.project_id:
            raise NotFoundError("Embedding provider credential not found")
        if _value(credential.status) != _value(CredentialStatus.active):
            raise ConflictError("Embedding provider credential must be active")

        embedding_config = {
            "provider_model_id": str(provider_model.id),
            "provider": _value(credential.provider),
            "model": provider_model.model,
            "dimensions": dimensions,
        }
        build_config = _normalize_build_config(
            input_dto,
            embedding=embedding_config,
        )
        chunking = RAGChunkingConfig.model_validate(build_config["chunking"])
        parser_config = RAGParserConfig.model_validate(build_config["parser"])

        existing_snapshots = await self._snapshot_repo.list_by_collection(
            input_dto.project_id,
            input_dto.collection_id,
        )
        version = input_dto.version or _next_version(existing_snapshots)
        existing = await self._snapshot_repo.get_by_collection_version(
            input_dto.project_id,
            input_dto.collection_id,
            version,
        )
        if existing is not None:
            raise ConflictError(
                "Vector snapshot version already exists for this collection"
            )

        snapshot = VectorSnapshot(
            project_id=input_dto.project_id,
            collection_id=input_dto.collection_id,
            version=version,
            description=input_dto.description,
            embedding_provider_model_id=provider_model.id,
            embedding_provider=_value(credential.provider),
            embedding_model=provider_model.model,
            embedding_dimensions=dimensions,
            chunk_size=chunking.chunk_size,
            chunk_overlap=chunking.chunk_overlap,
            chunking_strategy=chunking.strategy,
            parser_config=parser_config.model_dump(),
            build_config=build_config,
            build_config_hash=_json_hash(build_config),
            document_count=len(active_documents),
            total_document_count=len(active_documents),
            created_by=input_dto.created_by,
        )
        created = await self._snapshot_repo.create(snapshot)
        frozen_documents = [
            VectorSnapshotDocument(
                vector_snapshot_id=created.id,
                document_id=document.id,
                document_sha256=_document_sha256(document),
                document_title=document.title,
                file_name=document.file_name,
                parser=_value(document.parser),
                status_at_build=_value(document.status),
                chunk_count=0,
            )
            for document in active_documents
        ]
        await self._snapshot_repo.add_snapshot_documents(frozen_documents)
        return _snapshot_to_output(created)


class ListVectorSnapshotsUseCase:
    def __init__(self, snapshot_repo: Any) -> None:
        self._snapshot_repo = snapshot_repo

    async def execute(
        self,
        input_dto: ListVectorSnapshotsInput,
    ) -> list[VectorSnapshotOutput]:
        snapshots = await self._snapshot_repo.list_by_collection(
            input_dto.project_id,
            input_dto.collection_id,
        )
        return [_snapshot_to_output(snapshot) for snapshot in snapshots]


class GetVectorSnapshotUseCase:
    def __init__(self, snapshot_repo: Any) -> None:
        self._snapshot_repo = snapshot_repo

    async def execute(
        self,
        input_dto: GetVectorSnapshotInput,
    ) -> VectorSnapshotOutput:
        snapshot = await self._snapshot_repo.get_by_id(input_dto.snapshot_id)
        if snapshot is None:
            raise NotFoundError("Vector snapshot not found")
        if input_dto.project_id and snapshot.project_id != input_dto.project_id:
            raise NotFoundError("Vector snapshot not found")
        return _snapshot_to_output(snapshot)


class GetCollectionOverviewUseCase:
    def __init__(
        self,
        *,
        snapshot_repo: Any,
        collection_repo: DocumentCollectionRepository,
        document_repo: DocumentRepository,
    ) -> None:
        self._snapshot_repo = snapshot_repo
        self._collection_repo = collection_repo
        self._document_repo = document_repo

    async def execute(
        self,
        input_dto: GetCollectionOverviewInput,
    ) -> CollectionOverviewOutput:
        collection = await self._collection_repo.get_by_id(input_dto.collection_id)
        if collection is None or collection.project_id != input_dto.project_id:
            raise NotFoundError("Document collection not found")

        documents = await self._document_repo.list_by_collection(
            input_dto.collection_id
        )
        active_documents = [
            document
            for document in documents
            if _value(document.status) != _value(DocumentStatus.DELETED)
        ]
        deleted_count = len(documents) - len(active_documents)
        ready_count = sum(
            1
            for document in active_documents
            if _value(document.status)
            in {_value(DocumentStatus.READY), "INDEXED"}
        )
        failed_count = sum(
            1
            for document in active_documents
            if _value(document.status) == "FAILED"
        )
        pending_count = max(
            len(active_documents) - ready_count - failed_count,
            0,
        )
        total_size = sum(
            int(getattr(document, "size_bytes", 0) or 0)
            for document in active_documents
        )

        snapshots = await self._snapshot_repo.list_by_collection(
            input_dto.project_id,
            input_dto.collection_id,
        )
        latest_snapshot = snapshots[0] if snapshots else None
        latest_ready = next(
            (
                snapshot
                for snapshot in snapshots
                if snapshot.status == VECTOR_SNAPSHOT_READY
            ),
            None,
        )
        building = next(
            (
                snapshot
                for snapshot in snapshots
                if snapshot.status == VECTOR_SNAPSHOT_BUILDING
            ),
            None,
        )

        warnings: list[str] = []
        if not active_documents:
            rag_status = "EMPTY"
        elif building is not None:
            rag_status = "BUILDING"
        elif (
            latest_snapshot is not None
            and latest_snapshot.status == VECTOR_SNAPSHOT_FAILED
            and latest_ready is None
        ):
            rag_status = "FAILED"
        elif latest_ready is None:
            rag_status = "NEEDS_VECTORS"
        else:
            latest_ready_completed = (
                latest_ready.completed_at or latest_ready.created_at
            )
            changed_after_snapshot = False
            if latest_ready_completed is not None:
                for document in active_documents:
                    changed_at = document.updated_at or document.created_at
                    if changed_at and changed_at > latest_ready_completed:
                        changed_after_snapshot = True
                        break
            rag_status = "OUTDATED" if changed_after_snapshot else "READY"
            if changed_after_snapshot:
                warnings.append(
                    "Documents changed after the latest READY vector snapshot."
                )

        source_snapshot = building or latest_ready or latest_snapshot
        technology = CollectionOverviewTechnologyOutput(
            embedding_provider_model_id=(
                source_snapshot.embedding_provider_model_id
                if source_snapshot
                else None
            ),
            embedding_provider=(
                source_snapshot.embedding_provider if source_snapshot else None
            ),
            embedding_model=(
                source_snapshot.embedding_model if source_snapshot else None
            ),
            embedding_dimensions=(
                source_snapshot.embedding_dimensions if source_snapshot else None
            ),
            chunking_strategy=(
                source_snapshot.chunking_strategy if source_snapshot else None
            ),
            chunk_size=(source_snapshot.chunk_size if source_snapshot else None),
            chunk_overlap=(
                source_snapshot.chunk_overlap if source_snapshot else None
            ),
        )
        processing = CollectionOverviewProcessingOutput(
            has_running_job=building is not None,
            stage=building.build_stage if building else None,
            processed_documents=(
                building.processed_document_count
                if building
                else latest_ready.document_count
                if latest_ready
                else 0
            ),
            total_documents=(
                building.total_document_count
                if building
                else len(active_documents)
            ),
            processed_chunks=(
                building.processed_chunk_count
                if building
                else latest_ready.chunk_count
                if latest_ready
                else 0
            ),
            total_chunks=(
                building.total_chunk_count
                if building
                else latest_ready.chunk_count
                if latest_ready
                else 0
            ),
            embedded_chunks=(
                building.embedded_chunk_count
                if building
                else latest_ready.vector_count
                if latest_ready
                else 0
            ),
        )
        return CollectionOverviewOutput(
            collection_id=input_dto.collection_id,
            project_id=input_dto.project_id,
            rag_status=rag_status,
            documents=CollectionOverviewDocumentsOutput(
                active=len(active_documents),
                ready=ready_count,
                failed=failed_count,
                pending=pending_count,
                deleted=deleted_count,
                total_size_bytes=total_size,
            ),
            latest_snapshot=(
                _snapshot_to_output(latest_snapshot)
                if latest_snapshot
                else None
            ),
            latest_ready_snapshot=(
                _snapshot_to_output(latest_ready) if latest_ready else None
            ),
            processing=processing,
            technology=technology,
            warnings=warnings,
        )


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
        encryption_key: str,
        parser: DocumentParser | None = None,
        chunker: RecursiveTextChunker | None = None,
    ) -> None:
        self._snapshot_repo = snapshot_repo
        self._document_repo = document_repo
        self._provider_model_repo = provider_model_repo
        self._credential_repo = credential_repo
        self._storage = storage
        self._embedding_factory = embedding_factory
        self._encryption_key = encryption_key
        self._parser = parser or DocumentParser()
        self._chunker = chunker or RecursiveTextChunker()

    async def execute(self, snapshot_id: UUID) -> VectorSnapshotOutput:
        snapshot = await self._snapshot_repo.get_by_id(snapshot_id)
        if snapshot is None:
            raise NotFoundError("Vector snapshot not found")
        if snapshot.status != VECTOR_SNAPSHOT_BUILDING:
            raise ConflictError(
                "Only BUILDING vector snapshots can be processed"
            )

        await self._snapshot_repo.mark_started(snapshot.id)
        try:
            return await self._build(snapshot)
        except Exception as exc:
            await self._snapshot_repo.mark_failed(snapshot.id, str(exc))
            raise

    async def _build(self, snapshot: VectorSnapshot) -> VectorSnapshotOutput:
        provider_model = await self._provider_model_repo.get_by_id(
            snapshot.embedding_provider_model_id
        )
        if provider_model is None:
            raise NotFoundError("Embedding provider model not found")
        credential = await self._credential_repo.get_by_id(
            provider_model.provider_credential_id
        )
        if credential is None:
            raise NotFoundError("Embedding provider credential not found")

        api_key = decrypt_secret(
            credential.encrypted_secret,
            self._encryption_key,
        )
        metadata = provider_model.metadata or {}
        base_url = metadata.get("base_url") or (
            credential.metadata or {}
        ).get("base_url")
        embedding_client = self._embedding_factory.create_embedding_client(
            provider=snapshot.embedding_provider,
            model=snapshot.embedding_model,
            api_key=api_key,
            base_url=base_url,
            dimensions=snapshot.embedding_dimensions,
        )
        chunking = _snapshot_chunking_config(snapshot)
        parser_config = _snapshot_parser_config(snapshot)

        snapshot_documents = await self._snapshot_repo.list_snapshot_documents(
            snapshot.id
        )
        if not snapshot_documents:
            documents = await self._document_repo.list_by_collection(
                snapshot.collection_id
            )
            active_documents = [
                document
                for document in documents
                if _value(document.status) != _value(DocumentStatus.DELETED)
            ]
            snapshot_documents = [
                VectorSnapshotDocument(
                    vector_snapshot_id=snapshot.id,
                    document_id=document.id,
                    document_sha256=_document_sha256(document),
                    document_title=document.title,
                    file_name=document.file_name,
                    parser=_value(document.parser),
                    status_at_build=_value(document.status),
                )
                for document in active_documents
            ]
            await self._snapshot_repo.add_snapshot_documents(snapshot_documents)

        if not snapshot_documents:
            raise ConflictError("Collection has no frozen documents to snapshot")

        await self._snapshot_repo.delete_snapshot_chunks(snapshot.id)
        await self._snapshot_repo.update_build_progress(
            snapshot.id,
            build_stage=VECTOR_SNAPSHOT_STAGE_PARSING,
            total_document_count=len(snapshot_documents),
            processed_document_count=0,
            total_chunk_count=0,
            processed_chunk_count=0,
            embedded_chunk_count=0,
        )

        snapshot_chunks: list[VectorSnapshotChunk] = []
        hash_documents: list[dict[str, Any]] = []
        processed_documents = 0
        total_chunks = 0
        embedded_chunks = 0

        for frozen_document in snapshot_documents:
            document = await self._document_repo.get_by_id(
                frozen_document.document_id
            )
            if document is None or document.project_id != snapshot.project_id:
                raise NotFoundError(
                    "Frozen snapshot document not found: "
                    f"{frozen_document.document_id}"
                )
            if not document.storage_key:
                raise ConflictError(
                    f"Document has no storage key: {document.id}"
                )

            await self._snapshot_repo.update_build_progress(
                snapshot.id,
                build_stage=VECTOR_SNAPSHOT_STAGE_PARSING,
                processed_document_count=processed_documents,
                total_chunk_count=total_chunks,
                processed_chunk_count=len(snapshot_chunks),
                embedded_chunk_count=embedded_chunks,
                current_document_id=document.id,
            )
            raw = await self._storage.read_document(document.storage_key)
            parsed = self._parser.parse(
                content=raw,
                parser=document.parser,
                file_name=document.file_name,
                config=parser_config.model_dump(),
            )

            await self._snapshot_repo.update_build_progress(
                snapshot.id,
                build_stage=VECTOR_SNAPSHOT_STAGE_CHUNKING,
                current_document_id=document.id,
            )
            text_chunks = self._chunker.chunk(
                parsed.text,
                chunk_size=chunking.chunk_size,
                chunk_overlap=chunking.chunk_overlap,
                strategy=chunking.strategy,
                min_chunk_size=chunking.min_chunk_size,
                preserve_paragraphs=chunking.preserve_paragraphs,
                preserve_headings=chunking.preserve_headings,
                preserve_page_boundaries=chunking.preserve_page_boundaries,
            )
            if not text_chunks:
                processed_documents += 1
                continue

            total_chunks += len(text_chunks)
            await self._snapshot_repo.update_build_progress(
                snapshot.id,
                build_stage=VECTOR_SNAPSHOT_STAGE_EMBEDDING,
                processed_document_count=processed_documents,
                total_chunk_count=total_chunks,
                processed_chunk_count=len(snapshot_chunks),
                embedded_chunk_count=embedded_chunks,
                current_document_id=document.id,
            )

            for batch_start in range(
                0,
                len(text_chunks),
                EMBEDDING_BATCH_SIZE,
            ):
                batch_chunks = text_chunks[
                    batch_start : batch_start + EMBEDDING_BATCH_SIZE
                ]
                texts = [chunk.content for chunk in batch_chunks]
                embeddings = await embedding_client.aembed_documents(texts)
                if len(embeddings) != len(batch_chunks):
                    raise ValidationError(
                        "Embedding provider returned an unexpected batch size"
                    )

                for chunk, embedding in zip(
                    batch_chunks,
                    embeddings,
                    strict=True,
                ):
                    if len(embedding) != snapshot.embedding_dimensions:
                        raise ConflictError(
                            "Embedding provider returned incompatible "
                            "vector dimensions"
                        )
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
                embedded_chunks += len(batch_chunks)
                await self._snapshot_repo.update_build_progress(
                    snapshot.id,
                    build_stage=VECTOR_SNAPSHOT_STAGE_EMBEDDING,
                    total_chunk_count=total_chunks,
                    processed_chunk_count=len(snapshot_chunks),
                    embedded_chunk_count=embedded_chunks,
                    current_document_id=document.id,
                )

            await self._snapshot_repo.update_snapshot_document_chunk_count(
                snapshot.id,
                document.id,
                len(text_chunks),
            )
            hash_documents.append(
                {
                    "document_id": str(document.id),
                    "sha256": _document_sha256(document),
                    "file_name": document.file_name,
                    "chunk_count": len(text_chunks),
                }
            )
            document.status = DocumentStatus.READY
            document.chunk_count = len(text_chunks)
            document.page_count = parsed.page_count
            document.indexed_at = utc_now()
            await self._document_repo.update(document)
            processed_documents += 1
            await self._snapshot_repo.update_build_progress(
                snapshot.id,
                processed_document_count=processed_documents,
                current_document_id=None,
            )

        if not snapshot_chunks:
            raise ConflictError("Vector snapshot build produced no chunks")

        await self._snapshot_repo.update_build_progress(
            snapshot.id,
            build_stage=VECTOR_SNAPSHOT_STAGE_WRITING,
        )
        await self._snapshot_repo.add_snapshot_chunks(snapshot_chunks)
        snapshot_hash = compute_snapshot_hash(
            documents=hash_documents,
            parameters={
                "embedding_provider_model_id": str(
                    snapshot.embedding_provider_model_id
                ),
                "embedding_provider": snapshot.embedding_provider,
                "embedding_model": snapshot.embedding_model,
                "embedding_dimensions": snapshot.embedding_dimensions,
                "chunk_size": snapshot.chunk_size,
                "chunk_overlap": snapshot.chunk_overlap,
                "chunking_strategy": snapshot.chunking_strategy,
                "parser_config": snapshot.parser_config or {},
                "build_config": snapshot.build_config or {},
            },
        )
        ready = await self._snapshot_repo.mark_ready(
            snapshot.id,
            snapshot_hash=snapshot_hash,
            document_count=processed_documents,
            chunk_count=len(snapshot_chunks),
            vector_count=embedded_chunks,
        )
        if ready is None:
            raise NotFoundError("Vector snapshot not found")
        return _snapshot_to_output(ready)


class SearchVectorSnapshotChunksUseCase:
    def __init__(self, snapshot_repo: Any) -> None:
        self._snapshot_repo = snapshot_repo

    async def execute(self, input_dto: SearchVectorSnapshotChunksInput):
        snapshot = await self._snapshot_repo.get_by_id(
            input_dto.vector_snapshot_id
        )
        if snapshot is None:
            raise NotFoundError("Vector snapshot not found")
        if snapshot.status != VECTOR_SNAPSHOT_READY:
            raise ConflictError(
                "Vector snapshot must be READY before search"
            )
        return await self._snapshot_repo.search_similar(
            vector_snapshot_id=input_dto.vector_snapshot_id,
            embedding=input_dto.embedding,
            limit=input_dto.limit,
            threshold=input_dto.threshold,
        )
