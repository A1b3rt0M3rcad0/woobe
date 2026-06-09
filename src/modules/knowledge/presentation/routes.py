from fastapi import APIRouter, Request as FastAPIRequest

from modules.knowledge.application.composers.attach_collection_composer import attach_collection_composer
from modules.knowledge.application.composers.create_collection_composer import create_collection_composer
from modules.knowledge.application.composers.create_knowledge_version_composer import create_knowledge_version_composer
from modules.knowledge.application.composers.detach_collection_composer import detach_collection_composer
from modules.knowledge.application.composers.get_collection_composer import get_collection_composer
from modules.knowledge.application.composers.get_document_composer import get_document_composer
from modules.knowledge.application.composers.list_agent_collections_composer import list_agent_collections_composer
from modules.knowledge.application.composers.list_collections_composer import list_collections_composer
from modules.knowledge.application.composers.list_documents_composer import list_documents_composer
from modules.knowledge.application.composers.list_knowledge_versions_composer import list_knowledge_versions_composer
from modules.knowledge.application.composers.search_chunks_composer import search_chunks_composer
from modules.knowledge.application.composers.upload_document_composer import upload_document_composer
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/collections")
async def list_collections(request: FastAPIRequest):
    handler = list_collections_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/collections")
async def create_collection(request: FastAPIRequest):
    handler = create_collection_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/collections/{collection_id}")
async def get_collection(request: FastAPIRequest):
    handler = get_collection_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agent-collections")
async def list_agent_collections(request: FastAPIRequest):
    handler = list_agent_collections_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agent-collections")
async def attach_collection(request: FastAPIRequest):
    handler = attach_collection_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.delete("/agent-collections/{link_id}")
async def detach_collection(request: FastAPIRequest):
    handler = detach_collection_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/documents")
async def list_documents(request: FastAPIRequest):
    handler = list_documents_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/documents")
async def upload_document(request: FastAPIRequest):
    handler = upload_document_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/documents/{document_id}")
async def get_document(request: FastAPIRequest):
    handler = get_document_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/search")
async def search_chunks(request: FastAPIRequest):
    handler = search_chunks_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents/{agent_id}/knowledge-versions", status_code=201)
async def create_knowledge_version(request: FastAPIRequest):
    handler = create_knowledge_version_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/knowledge-versions")
async def list_knowledge_versions(request: FastAPIRequest):
    handler = list_knowledge_versions_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)
