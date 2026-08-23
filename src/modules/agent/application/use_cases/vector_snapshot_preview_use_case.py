from __future__ import annotations

from modules.agent.application.dtos.rag_config_dtos import (
    VectorBuildPreviewOutput,
    VectorBuildPreviewSample,
)
from modules.agent.application.dtos.vector_snapshot_dtos import PreviewVectorSnapshotInput
from modules.agent.application.interfaces.file_storage import FileStorage
from modules.agent.application.interfaces.repositories import (
    DocumentCollectionRepository,
    DocumentRepository,
)
from modules.agent.application.services.rag.chunker import RecursiveTextChunker
from modules.agent.application.services.rag.document_parser import DocumentParser
from modules.agent.domain.enums import DocumentStatus
from shared.contracts.errors import ConflictError, NotFoundError


def _value(value: object) -> str:
    return str(getattr(value, "value", value))


class PreviewVectorSnapshotUseCase:
    def __init__(
        self,
        *,
        collection_repo: DocumentCollectionRepository,
        document_repo: DocumentRepository,
        storage: FileStorage,
        parser: DocumentParser | None = None,
        chunker: RecursiveTextChunker | None = None,
    ) -> None:
        self._collection_repo = collection_repo
        self._document_repo = document_repo
        self._storage = storage
        self._parser = parser or DocumentParser()
        self._chunker = chunker or RecursiveTextChunker()

    async def execute(
        self,
        input_dto: PreviewVectorSnapshotInput,
    ) -> VectorBuildPreviewOutput:
        collection = await self._collection_repo.get_by_id(input_dto.collection_id)
        if collection is None or collection.project_id != input_dto.project_id:
            raise NotFoundError("Document collection not found")

        documents = await self._document_repo.list_by_collection(input_dto.collection_id)
        active_documents = [
            document
            for document in documents
            if _value(document.status) != _value(DocumentStatus.DELETED)
        ]
        if not active_documents:
            raise ConflictError("Collection has no active documents to preview")

        parser_config = input_dto.parser.model_dump()
        chunking = input_dto.chunking
        total_chunks = 0
        samples: list[VectorBuildPreviewSample] = []

        for document in active_documents:
            if not document.storage_key:
                raise ConflictError(f"Document has no storage key: {document.id}")
            raw = await self._storage.read_document(document.storage_key)
            parsed = self._parser.parse(
                content=raw,
                parser=document.parser,
                file_name=document.file_name,
                config=parser_config,
            )
            chunks = self._chunker.chunk(
                parsed.text,
                chunk_size=chunking.chunk_size,
                chunk_overlap=chunking.chunk_overlap,
                strategy=chunking.strategy,
                min_chunk_size=chunking.min_chunk_size,
                preserve_paragraphs=chunking.preserve_paragraphs,
                preserve_headings=chunking.preserve_headings,
                preserve_page_boundaries=chunking.preserve_page_boundaries,
            )
            total_chunks += len(chunks)
            for chunk in chunks:
                if len(samples) >= 8:
                    break
                samples.append(
                    VectorBuildPreviewSample(
                        document_id=str(document.id),
                        document_title=document.title,
                        chunk_index=chunk.chunk_index,
                        character_count=len(chunk.content),
                        preview=chunk.content[:320],
                    )
                )

        return VectorBuildPreviewOutput(
            document_count=len(active_documents),
            estimated_chunk_count=total_chunks,
            estimated_vector_count=total_chunks,
            sample_chunks=samples,
        )
