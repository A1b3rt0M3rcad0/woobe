from uuid import UUID

from fastapi import APIRouter, File, Form, Request as FastAPIRequest, UploadFile
from modules.agent.entrypoint import create_provider_credential_composer
from modules.core.entrypoint import build_project_access_service
from modules.agent.entrypoint import list_provider_credentials_composer
from modules.agent.entrypoint import update_provider_credential_composer
from modules.agent.entrypoint import create_provider_model_composer
from modules.agent.entrypoint import list_provider_models_composer
from modules.agent.entrypoint import get_provider_model_composer
from modules.agent.entrypoint import update_provider_model_composer
from modules.agent.entrypoint import create_agent_composer
from modules.agent.entrypoint import list_agents_composer
from modules.agent.entrypoint import get_agent_composer
from modules.agent.entrypoint import update_agent_composer
from modules.agent.entrypoint import create_prompt_version_composer
from modules.agent.entrypoint import list_prompt_versions_composer
from modules.agent.entrypoint import get_prompt_version_composer
from modules.agent.entrypoint import create_contract_version_composer
from modules.agent.entrypoint import update_contract_version_composer
from modules.agent.entrypoint import list_contract_versions_composer
from modules.agent.entrypoint import get_contract_version_composer
from modules.agent.entrypoint import create_model_config_composer
from modules.agent.entrypoint import list_model_configs_composer
from modules.agent.entrypoint import get_model_config_composer
from modules.agent.entrypoint import create_release_composer
from modules.agent.entrypoint import list_releases_composer
from modules.agent.entrypoint import get_release_composer
from modules.agent.entrypoint import promote_release_composer
from modules.agent.entrypoint import rollback_release_composer
from modules.agent.entrypoint import delete_release_composer
from modules.agent.entrypoint import create_release_test_composer
from modules.agent.entrypoint import list_release_tests_composer
from modules.agent.entrypoint import attach_collection_composer
from modules.agent.entrypoint import create_collection_composer
from modules.agent.entrypoint import create_knowledge_version_composer
from modules.agent.entrypoint import detach_collection_composer
from modules.agent.entrypoint import get_collection_composer
from modules.agent.entrypoint import get_document_composer
from modules.agent.entrypoint import list_agent_collections_composer
from modules.agent.entrypoint import list_collections_composer
from modules.agent.entrypoint import list_documents_composer
from modules.agent.entrypoint import list_knowledge_versions_composer
from modules.agent.entrypoint import search_chunks_composer
from modules.agent.entrypoint import upload_document_composer
from modules.agent.entrypoint import update_collection_composer
from modules.agent.entrypoint import ask_agent_composer
from modules.agent.entrypoint import build_agent_stream_components
from modules.agent.entrypoint import create_ask_job_composer
from modules.agent.entrypoint import create_session_composer
from modules.agent.entrypoint import get_ask_job_composer
from modules.agent.entrypoint import list_agent_sessions_composer
from modules.agent.entrypoint import list_messages_composer
from modules.agent.entrypoint import send_message_composer
from woobe_api.http.agent import knowledge_files
from modules.agent.entrypoint import (
    create_secret_composer,
    create_tool_composer,
    delete_tool_composer,
    execute_tool_composer,
    list_secrets_composer,
    list_tools_by_agent_composer,
    list_tools_composer,
    test_tool_composer,
    update_tool_composer,
    update_tool_status_composer,
)
from woobe_api.http.shared.adapters import request_adapter, response_adapter
from shared.infra.errors import AuthenticationError
from woobe_api.http.agent.controllers.ask_agent_stream_controller import (
    AskAgentStreamController,
)

router = APIRouter(prefix="/ai", tags=["ai", "agent"])


@router.post("/credentials")
async def create_provider_credential(request: FastAPIRequest):
    handler = create_provider_credential_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/credentials/{credential_id}")
async def update_provider_credential(request: FastAPIRequest):
    handler = update_provider_credential_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/credentials")
async def list_provider_credentials(request: FastAPIRequest):
    handler = list_provider_credentials_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/provider-models", status_code=201)
async def create_provider_model(request: FastAPIRequest):
    handler = create_provider_model_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/provider-models")
async def list_provider_models(request: FastAPIRequest):
    handler = list_provider_models_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/provider-models/{provider_model_id}")
async def get_provider_model(request: FastAPIRequest):
    handler = get_provider_model_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/provider-models/{provider_model_id}")
async def update_provider_model(request: FastAPIRequest):
    handler = update_provider_model_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents")
async def create_agent(request: FastAPIRequest):
    handler = create_agent_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents")
async def list_agents(request: FastAPIRequest):
    handler = list_agents_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}")
async def get_agent(request: FastAPIRequest):
    handler = get_agent_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/agents/{agent_id}")
async def update_agent(request: FastAPIRequest):
    handler = update_agent_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents/{agent_id}/prompts", status_code=201)
async def create_prompt(request: FastAPIRequest):
    handler = create_prompt_version_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/prompts")
async def list_prompts(request: FastAPIRequest):
    handler = list_prompt_versions_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/prompts/{version_id}")
async def get_prompt(request: FastAPIRequest):
    handler = get_prompt_version_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents/{agent_id}/contracts", status_code=201)
async def create_contract(request: FastAPIRequest):
    handler = create_contract_version_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/agents/{agent_id}/contracts/{contract_id}")
async def update_contract(request: FastAPIRequest):
    handler = update_contract_version_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/contracts")
async def list_contracts(request: FastAPIRequest):
    handler = list_contract_versions_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/contracts/{contract_id}")
async def get_contract(request: FastAPIRequest):
    handler = get_contract_version_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents/{agent_id}/model-configs", status_code=201)
async def create_model_config(request: FastAPIRequest):
    handler = create_model_config_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/model-configs")
async def list_model_configs(request: FastAPIRequest):
    handler = list_model_configs_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/model-configs/{config_id}")
async def get_model_config(request: FastAPIRequest):
    handler = get_model_config_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents/{agent_id}/releases", status_code=201)
async def create_release(request: FastAPIRequest):
    handler = create_release_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/releases")
async def list_releases(request: FastAPIRequest):
    handler = list_releases_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/releases/{release_id}")
async def get_release(request: FastAPIRequest):
    handler = get_release_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents/{agent_id}/releases/{release_id}/promote")
async def promote_release(request: FastAPIRequest):
    handler = promote_release_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents/{agent_id}/releases/{release_id}/rollback")
async def rollback_release(request: FastAPIRequest):
    handler = rollback_release_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.delete("/agents/{agent_id}/releases/{release_id}")
async def delete_release(request: FastAPIRequest):
    handler = delete_release_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents/{agent_id}/release-tests", status_code=201)
async def create_release_test(request: FastAPIRequest):
    handler = create_release_test_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/agents/{agent_id}/releases/{release_id}/tests")
async def list_release_tests(request: FastAPIRequest):
    handler = list_release_tests_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


knowledge_router = APIRouter(prefix="/knowledge", tags=["knowledge", "agent"])


@knowledge_router.get("/collections")
async def list_collections(request: FastAPIRequest):
    handler = list_collections_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.post("/collections")
async def create_collection(request: FastAPIRequest):
    handler = create_collection_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.get("/collections/{collection_id}")
async def get_collection(request: FastAPIRequest):
    handler = get_collection_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.patch("/collections/{collection_id}")
async def update_collection(request: FastAPIRequest):
    handler = update_collection_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.get("/agent-collections")
async def list_agent_collections(request: FastAPIRequest):
    handler = list_agent_collections_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.post("/agent-collections")
async def attach_collection(request: FastAPIRequest):
    handler = attach_collection_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.delete("/agent-collections/{link_id}")
async def detach_collection(request: FastAPIRequest):
    handler = detach_collection_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.get("/documents")
async def list_documents(request: FastAPIRequest):
    handler = list_documents_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.post("/documents")
async def upload_document(request: FastAPIRequest):
    handler = upload_document_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.post("/documents/upload", status_code=201)
async def upload_document_file(
    project_id: UUID = Form(...),
    collection_id: UUID = Form(...),
    title: str | None = Form(None),
    file: UploadFile = File(...),
):
    return await knowledge_files.upload_document_file(
        project_id=project_id,
        collection_id=collection_id,
        title=title,
        file=file,
    )


@knowledge_router.delete("/documents/{document_id}")
async def delete_document(document_id: UUID):
    return await knowledge_files.delete_document(document_id=document_id)


@knowledge_router.get("/documents/{document_id}")
async def get_document(request: FastAPIRequest):
    handler = get_document_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.post("/search")
async def search_chunks(request: FastAPIRequest):
    handler = search_chunks_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.post("/agents/{agent_id}/knowledge-versions", status_code=201)
async def create_knowledge_version(request: FastAPIRequest):
    handler = create_knowledge_version_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.get("/agents/{agent_id}/knowledge-versions")
async def list_knowledge_versions(request: FastAPIRequest):
    handler = list_knowledge_versions_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


runtime_router = APIRouter(prefix="/runtime", tags=["runtime", "agent"])


@runtime_router.post("/sessions")
async def create_session(request: FastAPIRequest):
    handler = create_session_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@runtime_router.get("/agents/{agent_id}/sessions")
async def list_agent_sessions(request: FastAPIRequest):
    handler = list_agent_sessions_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@runtime_router.post("/ask")
async def ask(request: FastAPIRequest):
    handler = ask_agent_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@runtime_router.post("/ask/stream")
async def ask_stream(request: FastAPIRequest):
    controller = AskAgentStreamController(*build_agent_stream_components())
    return await controller.handle(request)


@runtime_router.post("/ask/jobs", status_code=201)
async def create_ask_job(request: FastAPIRequest):
    handler = create_ask_job_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@runtime_router.get("/ask/jobs/{job_id}")
async def get_ask_job(request: FastAPIRequest):
    handler = get_ask_job_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@runtime_router.get("/sessions/{session_id}/messages")
async def list_messages(request: FastAPIRequest):
    handler = list_messages_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@runtime_router.post("/messages")
async def send_message(request: FastAPIRequest):
    handler = send_message_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


tools_router = APIRouter(prefix="/tools", tags=["tools"])


@tools_router.get("/tools")
async def tools_list_tools(request: FastAPIRequest):
    handler = list_tools_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.post("/tools")
async def tools_create_tool(request: FastAPIRequest):
    handler = create_tool_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.patch("/tools/{tool_id}")
async def tools_update_tool(request: FastAPIRequest):
    handler = update_tool_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.patch("/tools/{tool_id}/status")
async def tools_update_tool_status(request: FastAPIRequest):
    handler = update_tool_status_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.delete("/tools/{tool_id}")
async def tools_delete_tool(request: FastAPIRequest):
    handler = delete_tool_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.post("/tools/test")
async def tools_test_tool(request: FastAPIRequest):
    payload = await request.json()
    project_id = payload.get("project_id") if isinstance(payload, dict) else None
    if project_id is not None:
        try:
            project_uuid = UUID(str(project_id))
        except ValueError:
            # DTO validation below owns the client-facing invalid UUID response.
            project_uuid = None
        if project_uuid is not None:
            principal = getattr(request.state, "principal", None)
            user_id = getattr(principal, "user_id", None)
            if user_id is None:
                raise AuthenticationError("Authentication required")
            await build_project_access_service().require_project_access(
                user_id=UUID(str(user_id)),
                project_id=project_uuid,
            )

    handler = test_tool_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.post("/tools/execute")
async def tools_execute_tool(request: FastAPIRequest):
    handler = execute_tool_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.get("/agents/{agent_id}/tools")
async def tools_list_tools_by_agent(request: FastAPIRequest):
    handler = list_tools_by_agent_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.get("/secrets")
async def tools_list_secrets(request: FastAPIRequest):
    handler = list_secrets_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.post("/secrets")
async def tools_create_secret(request: FastAPIRequest):
    handler = create_secret_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


agent_router = APIRouter(prefix="/agent", tags=["agent"])
agent_router.include_router(router)
agent_router.include_router(knowledge_router)
agent_router.include_router(runtime_router)
