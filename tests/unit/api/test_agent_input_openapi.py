import inspect

import pytest
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder

from modules.agent import entrypoint
from woobe_api.http.agent import routes
from woobe_api.http.shared.openapi_contracts import request_body_contract


from woobe_api.http.agent import mcp_tools_routes

CONTRACT_OPTIONS = {}
EXTRA_ROUTERS = []

CONTRACT_OPTIONS['update_collection'] = {'required': False, 'path_fields': ('collection_id',)}

CONTRACT_OPTIONS['create_knowledge_version'] = {'required': True, 'path_fields': ('agent_id',)}

CONTRACT_OPTIONS['tools_update_tool_status'] = {'required': False}

CONTRACT_OPTIONS['tools_test_tool'] = {'required': True}

CONTRACT_OPTIONS['tools_execute_tool'] = {'required': True}

EXTRA_ROUTERS.append(mcp_tools_routes.router)

CONTRACT_OPTIONS['discover_mcp_tools'] = {'required': True}

CONTRACT_OPTIONS['refresh_mcp_tools'] = {'required': True}

CONTRACTS = [
    ('refresh_mcp_tools', 'RefreshMcpProviderToolsInput', '/tools/mcp/refresh', 'post'),
    ('discover_mcp_tools', 'McpDiscoverInput', '/tools/mcp/discover', 'post'),
    ('tools_execute_tool', 'ExecuteToolInput', '/tools/tools/execute', 'post'),
    ('tools_test_tool', 'TestToolInput', '/tools/tools/test', 'post'),
    ('tools_update_tool_status', 'UpdateToolStatusInput', '/tools/tools/{tool_id}/status', 'patch'),
    ('create_knowledge_version', 'CreateKnowledgeVersionInput', '/knowledge/agents/{agent_id}/knowledge-versions', 'post'),
    ('update_collection', 'UpdateCollectionInput', '/knowledge/collections/{collection_id}', 'patch'),
    ('tools_create_tool', 'CreateToolInput', '/tools/tools', 'post'),
    ('tools_update_tool', 'UpdateToolInput', '/tools/tools/{tool_id}', 'patch'),
    ('tools_create_secret', 'CreateSecretInput', '/tools/secrets', 'post'),

    ('create_session', 'CreateSessionInput', '/runtime/sessions', 'post'),
    ('send_message', 'SendMessageInput', '/runtime/messages', 'post'),
    ('create_ask_job', 'CreateAskJobInput', '/runtime/ask/jobs', 'post'),

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
    app.include_router(routes.tools_router)
    for extra_router in EXTRA_ROUTERS:
        app.include_router(extra_router)
    model = getattr(entrypoint, model_name)
    expected = request_body_contract(model, path, method, **CONTRACT_OPTIONS.get(endpoint, {"required": method != "patch"}))
    operation = app.openapi()["paths"][path][method]
    assert operation["requestBody"] == jsonable_encoder(expected["requestBody"], exclude_none=True)
    endpoint_function = next(route.endpoint for route in app.routes if getattr(route, "name", None) == endpoint)
    expected_args = ["request", "collection_id"] if endpoint in {"preview_vector_snapshot", "create_vector_snapshot"} else ["request"]
    assert list(inspect.signature(endpoint_function).parameters) == expected_args


def test_agent_session_query_contract_describes_the_consumed_dto_filters():
    app = FastAPI()
    app.include_router(routes.runtime_router)
    operation = app.openapi()["paths"]["/runtime/agents/{agent_id}/sessions"]["get"]
    parameters = {item["name"]: item for item in operation["parameters"]}
    properties = entrypoint.ListAgentSessionsInput.model_json_schema(mode="validation")["properties"]
    assert set(parameters) == {"agent_id", "project_id", "environment", "cursor", "limit"}
    for name, item in parameters.items():
        assert item["schema"] == jsonable_encoder(properties[name], exclude_none=True)
        assert item["required"] is (name in {"agent_id", "project_id"})
    assert parameters["agent_id"]["in"] == "path"
    assert parameters["limit"]["schema"]["maximum"] == 100


def test_all_advertised_dto_references_resolve_in_the_openapi_document():
    app = FastAPI()
    for router in (routes.router, routes.knowledge_router, routes.runtime_router, routes.tools_router, *EXTRA_ROUTERS):
        app.include_router(router)
    document = app.openapi()

    def inspect_references(value):
        if isinstance(value, dict):
            if "$ref" in value:
                target = document
                assert value["$ref"].startswith("#/")
                for segment in value["$ref"][2:].split("/"):
                    target = target[segment.replace("~1", "/").replace("~0", "~")]
                assert isinstance(target, dict)
            for key, child in value.items():
                if key not in {"default", "const", "enum", "examples", "example"}:
                    inspect_references(child)
        elif isinstance(value, list):
            for child in value:
                inspect_references(child)

    for _, _, path, method in CONTRACTS:
        inspect_references(document["paths"][path][method]["requestBody"])
