from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from modules.knowledge.application.providers import (
    provide_create_collection_uc,
    provide_get_collection,
    provide_get_document,
    provide_search_chunks_uc,
    provide_upload_document_uc,
)
from modules.knowledge.presentation.schemas import (
    ChunkResponse,
    CollectionResponse,
    CreateCollectionRequest,
    DocumentResponse,
    SearchRequest,
    UploadDocumentRequest,
)
from modules.knowledge.service.dtos import (
    CreateCollectionInput,
    SearchChunksInput,
    UploadDocumentInput,
)
from shared.domain.errors import ConflictError, NotFoundError, ValidationError
from shared.presentation.dependencies import get_session_manager
from shared.presentation.responses import created, error, ok

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/collections")
async def create_collection(
    body: CreateCollectionRequest,
    manager=Depends(get_session_manager),
):
    try:
        uc = provide_create_collection_uc(manager.session)
        dto = CreateCollectionInput(
            project_id=body.project_id,
            name=body.name,
            description=body.description,
        )
        result = await uc.execute(dto)
        return created(
            CollectionResponse(
                id=result.id,
                project_id=result.project_id,
                name=result.name,
                description=result.description,
                status=result.status,
                created_at=result.created_at,
                updated_at=result.updated_at,
            )
        )
    except ConflictError as e:
        return error(str(e), status_code=409)
    except ValidationError as e:
        return error(str(e), status_code=422)


@router.get("/collections/{collection_id}")
async def get_collection(
    collection_id: UUID,
    manager=Depends(get_session_manager),
):
    try:
        collection = await provide_get_collection(manager.session, collection_id)
        return ok(
            CollectionResponse(
                id=collection.id,
                project_id=collection.project_id,
                name=collection.name,
                description=collection.description,
                status=collection.status,
                created_at=collection.created_at,
                updated_at=collection.updated_at,
            )
        )
    except NotFoundError as e:
        return error(str(e), status_code=404)


@router.post("/documents")
async def upload_document(
    body: UploadDocumentRequest,
    manager=Depends(get_session_manager),
):
    try:
        uc = provide_upload_document_uc(manager.session)
        dto = UploadDocumentInput(
            project_id=body.project_id,
            collection_id=body.collection_id,
            title=body.title,
            file_name=body.file_name,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
            storage_key=body.storage_key,
        )
        result = await uc.execute(dto)
        return created(
            DocumentResponse(
                id=result.id,
                project_id=result.project_id,
                collection_id=result.collection_id,
                title=result.title,
                file_name=result.file_name,
                content_type=result.content_type,
                size_bytes=result.size_bytes,
                storage_key=result.storage_key,
                status=result.status,
                created_at=result.created_at,
                updated_at=result.updated_at,
            )
        )
    except NotFoundError as e:
        return error(str(e), status_code=404)
    except ValidationError as e:
        return error(str(e), status_code=422)


@router.get("/documents/{document_id}")
async def get_document(
    document_id: UUID,
    manager=Depends(get_session_manager),
):
    try:
        document = await provide_get_document(manager.session, document_id)
        return ok(
            DocumentResponse(
                id=document.id,
                project_id=document.project_id,
                collection_id=document.collection_id,
                title=document.title,
                file_name=document.file_name,
                content_type=document.content_type,
                size_bytes=document.size_bytes,
                storage_key=document.storage_key,
                status=document.status,
                created_at=document.created_at,
                updated_at=document.updated_at,
            )
        )
    except NotFoundError as e:
        return error(str(e), status_code=404)


@router.post("/search")
async def search_chunks(
    body: SearchRequest,
    manager=Depends(get_session_manager),
):
    try:
        uc = provide_search_chunks_uc(manager.session)
        dto = SearchChunksInput(
            collection_id=body.collection_id,
            embedding=[],
            limit=body.limit,
        )
        result = await uc.execute(dto)
        return ok(
            [
                ChunkResponse(
                    id=r.id,
                    content=r.content,
                    chunk_index=r.chunk_index,
                    token_count=r.token_count,
                    page_number=r.page_number,
                    section_title=r.section_title,
                    data=r.data,
                    score=r.similarity,
                )
                for r in result.results
            ]
        )
    except ValidationError as e:
        return error(str(e), status_code=422)
