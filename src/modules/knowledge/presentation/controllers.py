from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from modules.knowledge.application.providers import (
    provide_create_collection_uc,
    provide_get_collection,
    provide_get_document,
    provide_search_chunks_uc,
    provide_upload_document_uc,
)
from modules.knowledge.infra.mappers import model_to_document
from modules.knowledge.infra.repositories import (
    SQLAlchemyDocumentCollectionRepository,
    SQLAlchemyDocumentRepository,
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


@router.get("/collections")
async def list_collections(
    project_id: UUID | None = Query(None),
    manager=Depends(get_session_manager),
):
    if not project_id:
        return ok([])
    repo = SQLAlchemyDocumentCollectionRepository(manager.session)
    collections = await repo.list_by_project(project_id)
    return ok([CollectionResponse(
        id=c.id,
        project_id=c.project_id,
        name=c.name,
        description=c.description,
        status=c.status,
        created_at=c.created_at,
        updated_at=c.updated_at,
    ) for c in collections])


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


@router.get("/documents")
async def list_documents(
    project_id: UUID | None = Query(None),
    collection_id: UUID | None = Query(None),
    manager=Depends(get_session_manager),
):
    if not project_id and not collection_id:
        return ok([])
    from sqlalchemy import select
    from modules.knowledge.infra.models import DocumentModel
    repo = SQLAlchemyDocumentRepository(manager.session)
    if collection_id:
        documents = await repo.list_by_collection(collection_id)
    elif project_id:
        stmt = select(DocumentModel).where(DocumentModel.project_id == project_id).order_by(DocumentModel.created_at.desc())
        result = await manager.session.execute(stmt)
        documents = [model_to_document(m) for m in result.scalars().all()]
    else:
        documents = []
    return ok([DocumentResponse(
        id=d.id,
        project_id=d.project_id,
        collection_id=d.collection_id,
        title=d.title,
        file_name=d.file_name,
        content_type=d.content_type,
        size_bytes=d.size_bytes,
        storage_key=d.storage_key,
        status=d.status,
        created_at=d.created_at,
        updated_at=d.updated_at,
    ) for d in documents])


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
