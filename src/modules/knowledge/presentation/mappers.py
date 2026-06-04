from modules.knowledge.domain.entities import Document, DocumentCollection
from modules.knowledge.presentation.schemas import (
    AgentCollectionResponse,
    ChunkResponse,
    CollectionResponse,
    DocumentResponse,
)
from modules.knowledge.service.dtos import (
    AgentCollectionOutput,
    AttachCollectionOutput,
    CreateCollectionOutput,
    DocumentChunkOutput,
    UploadDocumentOutput,
)


def collection_to_response(collection: DocumentCollection) -> CollectionResponse:
    return CollectionResponse(
        id=collection.id,
        project_id=collection.project_id,
        name=collection.name,
        description=collection.description,
        status=collection.status,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


def create_collection_output_to_response(output: CreateCollectionOutput) -> CollectionResponse:
    return CollectionResponse(
        id=output.id,
        project_id=output.project_id,
        name=output.name,
        description=output.description,
        status=output.status,
        created_at=output.created_at,
        updated_at=output.updated_at,
    )


def agent_collection_output_to_response(output: AgentCollectionOutput) -> AgentCollectionResponse:
    return AgentCollectionResponse(
        id=output.id,
        agent_id=output.agent_id,
        collection_id=output.collection_id,
        created_at=output.created_at,
        updated_at=output.updated_at,
    )


def attach_collection_output_to_response(output: AttachCollectionOutput) -> AgentCollectionResponse:
    return AgentCollectionResponse(
        id=output.id,
        agent_id=output.agent_id,
        collection_id=output.collection_id,
        created_at=output.created_at,
        updated_at=output.updated_at,
    )


def document_to_response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        project_id=document.project_id,
        collection_id=document.collection_id,
        title=document.title,
        file_name=document.file_name,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        storage_key=document.storage_key,
        status=document.status,
        page_count=document.page_count,
        chunk_count=document.chunk_count,
        error=document.error,
        indexed_at=document.indexed_at,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def upload_document_output_to_response(output: UploadDocumentOutput) -> DocumentResponse:
    return DocumentResponse(
        id=output.id,
        project_id=output.project_id,
        collection_id=output.collection_id,
        title=output.title,
        file_name=output.file_name,
        content_type=output.content_type,
        size_bytes=output.size_bytes,
        storage_key=output.storage_key,
        status=output.status,
        page_count=output.page_count,
        chunk_count=output.chunk_count,
        error=output.error,
        indexed_at=output.indexed_at,
        created_at=output.created_at,
        updated_at=output.updated_at,
    )


def chunk_output_to_response(output: DocumentChunkOutput) -> ChunkResponse:
    return ChunkResponse(
        id=output.id,
        content=output.content,
        chunk_index=output.chunk_index,
        token_count=output.token_count,
        page_number=output.page_number,
        section_title=output.section_title,
        data=output.data,
        score=output.similarity,
    )
