from __future__ import annotations

from modules.knowledge.domain.entities import Document, DocumentChunk, DocumentCollection
from modules.knowledge.domain.enums import CollectionStatus, DocumentStatus, ParserType
from modules.knowledge.infra.models import DocumentChunkModel, DocumentCollectionModel, DocumentModel


def collection_to_model(entity: DocumentCollection) -> DocumentCollectionModel:
    return DocumentCollectionModel(
        id=entity.id,
        project_id=entity.project_id,
        name=entity.name,
        description=entity.description,
        status=entity.status.value if isinstance(entity.status, CollectionStatus) else entity.status,
    )


def model_to_collection(model: DocumentCollectionModel) -> DocumentCollection:
    return DocumentCollection(
        id=model.id,
        project_id=model.project_id,
        name=model.name,
        description=model.description,
        status=CollectionStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def document_to_model(entity: Document) -> DocumentModel:
    return DocumentModel(
        id=entity.id,
        project_id=entity.project_id,
        collection_id=entity.collection_id,
        title=entity.title,
        file_name=entity.file_name,
        content_type=entity.content_type,
        size_bytes=entity.size_bytes,
        storage_key=entity.storage_key,
        parser=entity.parser.value if isinstance(entity.parser, ParserType) else entity.parser,
        status=entity.status.value if isinstance(entity.status, DocumentStatus) else entity.status,
        error=entity.error,
        page_count=entity.page_count,
        chunk_count=entity.chunk_count,
        sha256=entity.sha256,
        indexed_at=entity.indexed_at,
    )


def model_to_document(model: DocumentModel) -> Document:
    return Document(
        id=model.id,
        project_id=model.project_id,
        collection_id=model.collection_id,
        title=model.title,
        file_name=model.file_name,
        content_type=model.content_type,
        size_bytes=model.size_bytes,
        storage_key=model.storage_key,
        parser=ParserType(model.parser),
        status=DocumentStatus(model.status),
        error=model.error,
        page_count=model.page_count,
        chunk_count=model.chunk_count,
        sha256=model.sha256,
        indexed_at=model.indexed_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def chunk_to_model(entity: DocumentChunk) -> DocumentChunkModel:
    return DocumentChunkModel(
        id=entity.id,
        project_id=entity.project_id,
        collection_id=entity.collection_id,
        document_id=entity.document_id,
        content=entity.content,
        chunk_index=entity.chunk_index,
        token_count=entity.token_count,
        page_number=entity.page_number,
        section_title=entity.section_title,
        data=entity.data,
        embedding=entity.embedding,
    )


def model_to_chunk(model: DocumentChunkModel) -> DocumentChunk:
    return DocumentChunk(
        id=model.id,
        project_id=model.project_id,
        collection_id=model.collection_id,
        document_id=model.document_id,
        content=model.content,
        chunk_index=model.chunk_index,
        token_count=model.token_count,
        page_number=model.page_number,
        section_title=model.section_title,
        data=model.data,
        embedding=model.embedding,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )

