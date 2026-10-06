from modules.agent.entrypoint import (PromoteReleaseInput, RollbackReleaseInput)
from modules.agent.entrypoint import (UpdateToolStatusInput, TestToolInput, ExecuteToolInput)
from modules.agent.entrypoint import (UpdateCollectionInput, CreateKnowledgeVersionInput)
from modules.agent.entrypoint import ListAgentSessionsInput
from modules.agent.entrypoint import (CreateToolInput,UpdateToolInput,CreateSecretInput)
from modules.agent.entrypoint import (CreateSessionInput,SendMessageInput,CreateAskJobInput)
from modules.agent.entrypoint import (UploadDocumentInput,SearchChunksInput)
from modules.agent.entrypoint import (CreateCollectionInput,AttachCollectionInput)
from modules.agent.entrypoint import (CreateModelConfigInput,CreateReleaseTestInput)
from modules.agent.entrypoint import (CreatePromptInput,CreateContractInput,UpdateContractInput)
from modules.agent.entrypoint import (CreateProviderCredentialInput,UpdateProviderCredentialInput,CreateProviderModelInput,UpdateProviderModelInput)
from modules.agent.entrypoint import (CreateAgentInput,UpdateAgentInput)
from woobe_api.http.shared.openapi_contracts import request_body_contract
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


@router.post("/credentials", openapi_extra=request_body_contract(CreateProviderCredentialInput, "/ai/credentials", "post", required=True))
async def create_provider_credential(request: FastAPIRequest):
    handler = create_provider_credential_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/credentials/{credential_id}", openapi_extra=request_body_contract(UpdateProviderCredentialInput, "/ai/credentials/{credential_id}", "patch", required=False))
async def update_provider_credential(request: FastAPIRequest):
    handler = update_provider_credential_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/credentials")
async def list_provider_credentials(request: FastAPIRequest):
    handler = list_provider_credentials_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/provider-models", status_code=201, openapi_extra=request_body_contract(CreateProviderModelInput, "/ai/provider-models", "post", required=True))
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


@router.patch("/provider-models/{provider_model_id}", openapi_extra=request_body_contract(UpdateProviderModelInput, "/ai/provider-models/{provider_model_id}", "patch", required=False))
async def update_provider_model(request: FastAPIRequest):
    handler = update_provider_model_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents", openapi_extra=request_body_contract(CreateAgentInput, "/ai/agents", "post", required=True))
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


@router.patch("/agents/{agent_id}", openapi_extra=request_body_contract(UpdateAgentInput, "/ai/agents/{agent_id}", "patch", required=False))
async def update_agent(request: FastAPIRequest):
    handler = update_agent_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.delete("/agents/{agent_id}")
async def delete_agent(request: FastAPIRequest):
    handler = update_agent_composer()
    response = await request_adapter(
        request,
        handler,
        metadata={"agent_operation": "archive"},
    )
    return response_adapter(response)


@router.post("/agents/{agent_id}/prompts", status_code=201, openapi_extra=request_body_contract(CreatePromptInput, "/ai/agents/{agent_id}/prompts", "post", required=True))
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


@router.post("/agents/{agent_id}/contracts", status_code=201, openapi_extra=request_body_contract(CreateContractInput, "/ai/agents/{agent_id}/contracts", "post", required=True))
async def create_contract(request: FastAPIRequest):
    handler = create_contract_version_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/agents/{agent_id}/contracts/{contract_id}", openapi_extra=request_body_contract(UpdateContractInput, "/ai/agents/{agent_id}/contracts/{contract_id}", "patch", required=False))
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


@router.post("/agents/{agent_id}/model-configs", status_code=201, openapi_extra=request_body_contract(CreateModelConfigInput, "/ai/agents/{agent_id}/model-configs", "post", required=True))
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


@router.post("/agents/{agent_id}/releases/{release_id}/promote", openapi_extra=request_body_contract(PromoteReleaseInput, '/ai/agents/{agent_id}/releases/{release_id}/promote', 'post', required=False))
async def promote_release(request: FastAPIRequest):
    handler = promote_release_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents/{agent_id}/releases/{release_id}/rollback", openapi_extra=request_body_contract(RollbackReleaseInput, '/ai/agents/{agent_id}/releases/{release_id}/rollback', 'post', required=False))
async def rollback_release(request: FastAPIRequest):
    handler = rollback_release_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.delete("/agents/{agent_id}/releases/{release_id}")
async def delete_release(request: FastAPIRequest):
    handler = delete_release_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/agents/{agent_id}/release-tests", status_code=201, openapi_extra=request_body_contract(CreateReleaseTestInput, "/ai/agents/{agent_id}/release-tests", "post", required=True))
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


@knowledge_router.post("/collections", openapi_extra=request_body_contract(CreateCollectionInput, "/knowledge/collections", "post", required=True))
async def create_collection(request: FastAPIRequest):
    handler = create_collection_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.get("/collections/{collection_id}")
async def get_collection(request: FastAPIRequest):
    handler = get_collection_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.patch("/collections/{collection_id}", openapi_extra=request_body_contract(UpdateCollectionInput, '/knowledge/collections/{collection_id}', 'patch', required=False, path_fields=('collection_id',)))
async def update_collection(request: FastAPIRequest):
    handler = update_collection_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.delete("/collections/{collection_id}")
async def delete_collection(request: FastAPIRequest):
    handler = update_collection_composer()
    response = await request_adapter(
        request,
        handler,
        metadata={"collection_operation": "delete"},
    )
    return response_adapter(response)


@knowledge_router.get("/agent-collections")
async def list_agent_collections(request: FastAPIRequest):
    handler = list_agent_collections_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.post("/agent-collections", openapi_extra=request_body_contract(AttachCollectionInput, "/knowledge/agent-collections", "post", required=True))
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


@knowledge_router.post("/documents", openapi_extra=request_body_contract(UploadDocumentInput, "/knowledge/documents", "post", required=True))
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


@knowledge_router.post("/search", openapi_extra=request_body_contract(SearchChunksInput, "/knowledge/search", "post", required=True))
async def search_chunks(request: FastAPIRequest):
    handler = search_chunks_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@knowledge_router.post("/agents/{agent_id}/knowledge-versions", status_code=201, openapi_extra=request_body_contract(CreateKnowledgeVersionInput, '/knowledge/agents/{agent_id}/knowledge-versions', 'post', required=True, path_fields=('agent_id',)))
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


@runtime_router.post("/sessions", openapi_extra=request_body_contract(CreateSessionInput, "/runtime/sessions", "post", required=True))
async def create_session(request: FastAPIRequest):
    handler = create_session_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@runtime_router.get(
    "/agents/{agent_id}/sessions",
    openapi_extra={"parameters": [
        {"name": name, "in": "path" if name == "agent_id" else "query",
         "required": name in {"agent_id", "project_id"}, "schema": schema}
        for name, schema in ListAgentSessionsInput.model_json_schema(mode="validation")["properties"].items()
    ]},
)
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


@runtime_router.post("/ask/jobs", status_code=201, openapi_extra=request_body_contract(CreateAskJobInput, "/runtime/ask/jobs", "post", required=True))
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


@runtime_router.post("/messages", openapi_extra=request_body_contract(SendMessageInput, "/runtime/messages", "post", required=True))
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


@tools_router.post("/tools", openapi_extra=request_body_contract(CreateToolInput, "/tools/tools", "post", required=True))
async def tools_create_tool(request: FastAPIRequest):
    handler = create_tool_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.patch("/tools/{tool_id}", openapi_extra=request_body_contract(UpdateToolInput, "/tools/tools/{tool_id}", "patch", required=False))
async def tools_update_tool(request: FastAPIRequest):
    handler = update_tool_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.patch("/tools/{tool_id}/status", openapi_extra=request_body_contract(UpdateToolStatusInput, '/tools/tools/{tool_id}/status', 'patch', required=False))
async def tools_update_tool_status(request: FastAPIRequest):
    handler = update_tool_status_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.delete("/tools/{tool_id}")
async def tools_delete_tool(request: FastAPIRequest):
    handler = delete_tool_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.post("/tools/test", openapi_extra=request_body_contract(TestToolInput, '/tools/tools/test', 'post', required=True))
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


@tools_router.post("/tools/execute", openapi_extra=request_body_contract(ExecuteToolInput, '/tools/tools/execute', 'post', required=True))
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


@tools_router.post("/secrets", openapi_extra=request_body_contract(CreateSecretInput, "/tools/secrets", "post", required=True))
async def tools_create_secret(request: FastAPIRequest):
    handler = create_secret_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)


agent_router = APIRouter(prefix="/agent", tags=["agent"])
agent_router.include_router(router)
agent_router.include_router(knowledge_router)
agent_router.include_router(runtime_router)
