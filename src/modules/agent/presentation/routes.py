from fastapi import APIRouter, Request as FastAPIRequest

from modules.agent.application.composers.create_provider_credential_composer import create_provider_credential_composer
from modules.agent.application.composers.list_provider_credentials_composer import list_provider_credentials_composer
from modules.agent.application.composers.update_provider_credential_composer import update_provider_credential_composer
from modules.agent.application.composers.create_agent_composer import create_agent_composer
from modules.agent.application.composers.list_agents_composer import list_agents_composer
from modules.agent.application.composers.get_agent_composer import get_agent_composer
from modules.agent.application.composers.update_agent_composer import update_agent_composer

from modules.agent.application.composers.create_prompt_version_composer import create_prompt_version_composer
from modules.agent.application.composers.list_prompt_versions_composer import list_prompt_versions_composer
from modules.agent.application.composers.get_prompt_version_composer import get_prompt_version_composer
from modules.agent.application.composers.create_contract_version_composer import create_contract_version_composer
from modules.agent.application.composers.update_contract_version_composer import update_contract_version_composer
from modules.agent.application.composers.list_contract_versions_composer import list_contract_versions_composer
from modules.agent.application.composers.get_contract_version_composer import get_contract_version_composer
from modules.agent.application.composers.create_model_config_composer import create_model_config_composer
from modules.agent.application.composers.list_model_configs_composer import list_model_configs_composer
from modules.agent.application.composers.get_model_config_composer import get_model_config_composer
from modules.agent.application.composers.create_release_composer import create_release_composer
from modules.agent.application.composers.list_releases_composer import list_releases_composer
from modules.agent.application.composers.get_release_composer import get_release_composer
from modules.agent.application.composers.promote_release_composer import promote_release_composer
from modules.agent.application.composers.rollback_release_composer import rollback_release_composer
from modules.agent.application.composers.delete_release_composer import delete_release_composer
from modules.agent.application.composers.create_release_test_composer import create_release_test_composer
from modules.agent.application.composers.list_release_tests_composer import list_release_tests_composer
from modules.agent.application.composers.attach_collection_composer import attach_collection_composer
from modules.agent.application.composers.create_collection_composer import create_collection_composer
from modules.agent.application.composers.create_knowledge_version_composer import create_knowledge_version_composer
from modules.agent.application.composers.detach_collection_composer import detach_collection_composer
from modules.agent.application.composers.get_collection_composer import get_collection_composer
from modules.agent.application.composers.get_document_composer import get_document_composer
from modules.agent.application.composers.list_agent_collections_composer import list_agent_collections_composer
from modules.agent.application.composers.list_collections_composer import list_collections_composer
from modules.agent.application.composers.list_documents_composer import list_documents_composer
from modules.agent.application.composers.list_knowledge_versions_composer import list_knowledge_versions_composer
from modules.agent.application.composers.search_chunks_composer import search_chunks_composer
from modules.agent.application.composers.upload_document_composer import upload_document_composer
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/credentials")
async def create_provider_credential(request: FastAPIRequest):
    handler = create_provider_credential_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/credentials/{credential_id}")
async def update_provider_credential(request: FastAPIRequest):
    handler = update_provider_credential_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/credentials")
async def list_provider_credentials(request: FastAPIRequest):
    handler = list_provider_credentials_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents")
async def create_agent(request: FastAPIRequest):
    handler = create_agent_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents")
async def list_agents(request: FastAPIRequest):
    handler = list_agents_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}")
async def get_agent(request: FastAPIRequest):
    handler = get_agent_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/agents/{agent_id}")
async def update_agent(request: FastAPIRequest):
    handler = update_agent_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents/{agent_id}/prompts", status_code=201)
async def create_prompt(request: FastAPIRequest):
    handler = create_prompt_version_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/prompts")
async def list_prompts(request: FastAPIRequest):
    handler = list_prompt_versions_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/prompts/{version_id}")
async def get_prompt(request: FastAPIRequest):
    handler = get_prompt_version_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents/{agent_id}/contracts", status_code=201)
async def create_contract(request: FastAPIRequest):
    handler = create_contract_version_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/agents/{agent_id}/contracts/{contract_id}")
async def update_contract(request: FastAPIRequest):
    handler = update_contract_version_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/contracts")
async def list_contracts(request: FastAPIRequest):
    handler = list_contract_versions_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/contracts/{contract_id}")
async def get_contract(request: FastAPIRequest):
    handler = get_contract_version_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents/{agent_id}/model-configs", status_code=201)
async def create_model_config(request: FastAPIRequest):
    handler = create_model_config_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/model-configs")
async def list_model_configs(request: FastAPIRequest):
    handler = list_model_configs_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/model-configs/{config_id}")
async def get_model_config(request: FastAPIRequest):
    handler = get_model_config_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents/{agent_id}/releases", status_code=201)
async def create_release(request: FastAPIRequest):
    handler = create_release_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/releases")
async def list_releases(request: FastAPIRequest):
    handler = list_releases_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/releases/{release_id}")
async def get_release(request: FastAPIRequest):
    handler = get_release_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents/{agent_id}/releases/{release_id}/promote")
async def promote_release(request: FastAPIRequest):
    handler = promote_release_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents/{agent_id}/releases/{release_id}/rollback")
async def rollback_release(request: FastAPIRequest):
    handler = rollback_release_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.delete("/agents/{agent_id}/releases/{release_id}")
async def delete_release(request: FastAPIRequest):
    handler = delete_release_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents/{agent_id}/release-tests", status_code=201)
async def create_release_test(request: FastAPIRequest):
    handler = create_release_test_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/releases/{release_id}/tests")
async def list_release_tests(request: FastAPIRequest):
    handler = list_release_tests_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


knowledge_router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@knowledge_router.get("/collections")
async def list_collections(request: FastAPIRequest):
    handler = list_collections_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.post("/collections")
async def create_collection(request: FastAPIRequest):
    handler = create_collection_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.get("/collections/{collection_id}")
async def get_collection(request: FastAPIRequest):
    handler = get_collection_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.get("/agent-collections")
async def list_agent_collections(request: FastAPIRequest):
    handler = list_agent_collections_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.post("/agent-collections")
async def attach_collection(request: FastAPIRequest):
    handler = attach_collection_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.delete("/agent-collections/{link_id}")
async def detach_collection(request: FastAPIRequest):
    handler = detach_collection_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.get("/documents")
async def list_documents(request: FastAPIRequest):
    handler = list_documents_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.post("/documents")
async def upload_document(request: FastAPIRequest):
    handler = upload_document_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.get("/documents/{document_id}")
async def get_document(request: FastAPIRequest):
    handler = get_document_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.post("/search")
async def search_chunks(request: FastAPIRequest):
    handler = search_chunks_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.post("/agents/{agent_id}/knowledge-versions", status_code=201)
async def create_knowledge_version(request: FastAPIRequest):
    handler = create_knowledge_version_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.get("/agents/{agent_id}/knowledge-versions")
async def list_knowledge_versions(request: FastAPIRequest):
    handler = list_knowledge_versions_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)
