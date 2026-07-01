from uuid import UUID

from fastapi import APIRouter, File, Form, Request as FastAPIRequest, UploadFile
from fastapi.encoders import jsonable_encoder

from modules.agent.application.composers.create_provider_credential_composer import create_provider_credential_composer
from modules.agent.application.composers.list_provider_credentials_composer import list_provider_credentials_composer
from modules.agent.application.composers.update_provider_credential_composer import update_provider_credential_composer
from modules.agent.application.composers.create_provider_model_composer import create_provider_model_composer
from modules.agent.application.composers.list_provider_models_composer import list_provider_models_composer
from modules.agent.application.composers.get_provider_model_composer import get_provider_model_composer
from modules.agent.application.composers.update_provider_model_composer import update_provider_model_composer
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
from modules.agent.application.composers.ask_agent_composer import ask_agent_composer
from modules.agent.application.composers.ask_agent_stream_composer import ask_agent_stream_composer
from modules.agent.application.composers.create_ask_job_composer import create_ask_job_composer
from modules.agent.application.composers.create_session_composer import create_session_composer
from modules.agent.application.composers.get_ask_job_composer import get_ask_job_composer
from modules.agent.application.composers.list_agent_sessions_composer import list_agent_sessions_composer
from modules.agent.application.composers.list_messages_composer import list_messages_composer
from modules.agent.application.composers.send_message_composer import send_message_composer
from modules.agent.application.composers.tools_composers import (
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
from modules.agent.application.dtos import UploadDocumentFileInput
from modules.agent.application.use_cases import UploadDocumentFileUseCase
from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.storage.factory import create_file_storage
from modules.agent.presentation.mappers import upload_document_output_to_response
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/ai", tags=["ai", "agent"])


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


@router.post("/provider-models", status_code=201)
async def create_provider_model(request: FastAPIRequest):
    handler = create_provider_model_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/provider-models")
async def list_provider_models(request: FastAPIRequest):
    handler = list_provider_models_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/provider-models/{provider_model_id}")
async def get_provider_model(request: FastAPIRequest):
    handler = get_provider_model_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/provider-models/{provider_model_id}")
async def update_provider_model(request: FastAPIRequest):
    handler = update_provider_model_composer(request.app.state.session_factory)
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


knowledge_router = APIRouter(prefix="/knowledge", tags=["knowledge", "agent"])


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


@knowledge_router.post("/documents/upload", status_code=201)
async def upload_document_file(
    request: FastAPIRequest,
    project_id: UUID = Form(...),
    collection_id: UUID = Form(...),
    title: str | None = Form(None),
    file: UploadFile = File(...),
):
    settings = request.app.state.settings
    storage = create_file_storage(settings)
    async with AgentUnitOfWork(request.app.state.session_factory) as uow:
        use_case = UploadDocumentFileUseCase(
            doc_repo=uow.documents,
            collection_repo=uow.document_collections,
            outbox=SQLAlchemyAgentOutboxEventWriter(uow),
            storage=storage,
            settings=settings,
        )
        output = await use_case.execute(
            UploadDocumentFileInput(
                project_id=project_id,
                collection_id=collection_id,
                title=title,
            ),
            file,
        )

    return jsonable_encoder(
        {
            "success": True,
            "message": "created",
            "data": upload_document_output_to_response(output).model_dump(),
        }
    )


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


runtime_router = APIRouter(prefix="/runtime", tags=["runtime", "agent"])


@runtime_router.post("/sessions")
async def create_session(request: FastAPIRequest):
    handler = create_session_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@runtime_router.get("/agents/{agent_id}/sessions")
async def list_agent_sessions(request: FastAPIRequest):
    handler = list_agent_sessions_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@runtime_router.post("/ask")
async def ask(request: FastAPIRequest):
    handler = ask_agent_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@runtime_router.post("/ask/stream")
async def ask_stream(request: FastAPIRequest):
    handler = ask_agent_stream_composer(request.app.state.session_factory)
    return await handler(request)


@runtime_router.post("/ask/jobs", status_code=201)
async def create_ask_job(request: FastAPIRequest):
    handler = create_ask_job_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@runtime_router.get("/ask/jobs/{job_id}")
async def get_ask_job(request: FastAPIRequest):
    handler = get_ask_job_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@runtime_router.get("/sessions/{session_id}/messages")
async def list_messages(request: FastAPIRequest):
    handler = list_messages_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@runtime_router.post("/messages")
async def send_message(request: FastAPIRequest):
    handler = send_message_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


tools_router = APIRouter(prefix="/tools", tags=["tools"])


@tools_router.get("/tools")
async def tools_list_tools(request: FastAPIRequest):
    handler = list_tools_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.post("/tools")
async def tools_create_tool(request: FastAPIRequest):
    handler = create_tool_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.patch("/tools/{tool_id}")
async def tools_update_tool(request: FastAPIRequest):
    handler = update_tool_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.patch("/tools/{tool_id}/status")
async def tools_update_tool_status(request: FastAPIRequest):
    handler = update_tool_status_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.delete("/tools/{tool_id}")
async def tools_delete_tool(request: FastAPIRequest):
    handler = delete_tool_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.post("/tools/test")
async def tools_test_tool(request: FastAPIRequest):
    handler = test_tool_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.post("/tools/execute")
async def tools_execute_tool(request: FastAPIRequest):
    handler = execute_tool_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.get("/agents/{agent_id}/tools")
async def tools_list_tools_by_agent(request: FastAPIRequest):
    handler = list_tools_by_agent_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.get("/secrets")
async def tools_list_secrets(request: FastAPIRequest):
    handler = list_secrets_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@tools_router.post("/secrets")
async def tools_create_secret(request: FastAPIRequest):
    handler = create_secret_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


agent_router = APIRouter(prefix="/agent", tags=["agent"])
agent_router.include_router(router)
agent_router.include_router(knowledge_router)
agent_router.include_router(runtime_router)
