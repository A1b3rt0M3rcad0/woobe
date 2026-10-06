import inspect

import pytest
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder

from modules.agent import entrypoint
from woobe_api.http.agent import routes
from woobe_api.http.shared.openapi_contracts import request_body_contract


CONTRACTS = [
    ('upload_document', 'UploadDocumentInput', '/knowledge/documents', 'post'),
    ('search_chunks', 'SearchChunksInput', '/knowledge/search', 'post'),

    ('create_collection', 'CreateCollectionInput', '/knowledge/collections', 'post'),
    ('attach_collection', 'AttachCollectionInput', '/knowledge/agent-collections', 'post'),

    ('create_model_config', 'CreateModelConfigInput', '/ai/agents/{agent_id}/model-configs', 'post'),
    ('create_release_test', 'CreateReleaseTestInput', '/ai/agents/{agent_id}/release-tests', 'post'),

    ('create_prompt', 'CreatePromptInput', '/ai/agents/{agent_id}/prompts', 'post'),
    ('create_contract', 'CreateContractInput', '/ai/agents/{agent_id}/contracts', 'post'),
    ('update_contract', 'UpdateContractInput', '/ai/agents/{agent_id}/contracts/{contract_id}', 'patch'),

    ('create_provider_credential', 'CreateProviderCredentialInput', '/ai/credentials', 'post'),
    ('update_provider_credential', 'UpdateProviderCredentialInput', '/ai/credentials/{credential_id}', 'patch'),
    ('create_provider_model', 'CreateProviderModelInput', '/ai/provider-models', 'post'),
    ('update_provider_model', 'UpdateProviderModelInput', '/ai/provider-models/{provider_model_id}', 'patch'),

    ('create_agent', 'CreateAgentInput', '/ai/agents', 'post'),
    ('update_agent', 'UpdateAgentInput', '/ai/agents/{agent_id}', 'patch'),
]


@pytest.mark.parametrize("endpoint,model_name,path,method", CONTRACTS)
def test_agent_input_schema_uses_the_same_public_dto(endpoint, model_name, path, method):
    app = FastAPI()
    app.include_router(routes.router)
    app.include_router(routes.knowledge_router)
    app.include_router(routes.runtime_router)
    model = getattr(entrypoint, model_name)
    expected = request_body_contract(model, path, method, required=method != "patch")
    operation = app.openapi()["paths"][path][method]
    assert operation["requestBody"] == jsonable_encoder(expected["requestBody"], exclude_none=True)
    assert list(inspect.signature(getattr(routes, endpoint)).parameters) == ["request"]
