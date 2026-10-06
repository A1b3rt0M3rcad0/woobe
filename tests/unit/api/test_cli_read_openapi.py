import pytest
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from modules.agent import entrypoint
from woobe_api.http.agent import routes

CASES = [('ListAgentsInput', '/ai/agents'), ('GetAgentInput', '/ai/agents/{agent_id}')]
CASES += [('ListProviderCredentialsInput', '/ai/credentials'), ('ListProviderModelsInput', '/ai/provider-models')]
CASES += [('ListCollectionsInput', '/knowledge/collections'), ('GetCollectionInput', '/knowledge/collections/{collection_id}'), ('ListDocumentsInput', '/knowledge/documents'), ('GetDocumentInput', '/knowledge/documents/{document_id}')]

@pytest.mark.parametrize("model_name,path", CASES)
def test_read_contracts_include_consumed_dto_parameters(model_name,path):
    app=FastAPI()
    for router in [routes.router,routes.knowledge_router,routes.runtime_router,routes.tools_router]:app.include_router(router)
    operation=app.openapi()["paths"][path]["get"]
    assert "requestBody" not in operation
    params=operation["parameters"]
    assert len(params)==len({(p["name"],p["in"]) for p in params})
    properties=getattr(entrypoint,model_name).model_json_schema(mode="validation")["properties"]
    assert {p["name"] for p in params}==set(properties)
    for param in params:
        assert param["schema"]==jsonable_encoder(properties[param["name"]],exclude_none=True)
        assert param["in"]==("path" if "{"+param["name"]+"}" in path else "query")
