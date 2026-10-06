from pydantic import BaseModel

from woobe_api.http.shared.openapi_contracts import request_body_contract


class Child(BaseModel):
    name: str


class Parent(BaseModel):
    child: Child


def test_nested_dto_references_address_the_inline_openapi_schema() -> None:
    contract = request_body_contract(Parent, "/ai/agents/{agent_id}", "POST")
    schema = contract["requestBody"]["content"]["application/json"]["schema"]
    assert schema["properties"]["child"]["$ref"] == (
        "#/paths/~1ai~1agents~1{agent_id}/post/requestBody/content/application~1json/schema/$defs/Child"
    )
    assert schema["$defs"]["Child"] == Child.model_json_schema(mode="validation")
    assert Parent.model_json_schema()["properties"]["child"]["$ref"] == "#/$defs/Child"


def test_body_contract_advertises_path_identity_without_adding_body_fields() -> None:
    contract = request_body_contract(Child, "/ai/agents/{agent_id}", "PATCH", required=False)
    assert contract["requestBody"]["required"] is False
    assert contract["parameters"] == [{"name": "agent_id", "in": "path", "required": True, "schema": {"type": "string", "format": "uuid"}}]
    assert "agent_id" not in contract["requestBody"]["content"]["application/json"]["schema"]["properties"]


def test_relocation_preserves_literal_json_reference_values() -> None:
    class WithLiteral(Parent):
        @classmethod
        def model_json_schema(cls, **kwargs):
            schema = Parent.model_json_schema(**kwargs)
            schema["properties"]["config"] = {"type": "object", "default": {"$ref": "#/$defs/External"}}
            return schema

    schema = request_body_contract(WithLiteral, "/ai/agents", "post")["requestBody"]["content"]["application/json"]["schema"]
    assert schema["properties"]["config"]["default"] == {"$ref": "#/$defs/External"}
    assert schema["properties"]["child"]["$ref"].startswith("#/paths/~1ai~1agents/")


def test_route_injected_dto_identity_is_not_required_in_body():
    from uuid import UUID
    import pytest
    class BoundInput(BaseModel):
        collection_id: UUID
        name: str
    contract = request_body_contract(BoundInput, "/collections/{collection_id}", "patch", path_fields=("collection_id",))
    schema = contract["requestBody"]["content"]["application/json"]["schema"]
    assert schema["required"] == ["name"]
    assert "collection_id" not in schema["properties"]
    assert contract["parameters"][0]["schema"]["format"] == "uuid"
    assert "collection_id" in BoundInput.model_json_schema()["properties"]
    with pytest.raises(ValueError):
        request_body_contract(BoundInput, "/collections", "post", path_fields=("collection_id",))


def test_relocation_distinguishes_schema_keywords_from_property_names():
    from pydantic import Field
    class KeywordProperties(BaseModel):
        default: Child
        enum: Child
        reference: Child = Field(alias="$ref")
    schema = request_body_contract(KeywordProperties, "/contracts", "post")["requestBody"]["content"]["application/json"]["schema"]
    for name in ("default", "enum", "$ref"):
        assert schema["properties"][name]["$ref"] == "#/paths/~1contracts/post/requestBody/content/application~1json/schema/$defs/Child"


def test_server_injected_actor_fields_are_omitted_without_mutating_the_dto():
    from uuid import UUID

    class Input(BaseModel):
        project_id: UUID
        created_by_user_id: UUID
        name: str

    contract = request_body_contract(
        Input, "/projects/{project_id}", "post",
        path_fields=("project_id",), server_fields=("created_by_user_id",),
    )
    body = contract["requestBody"]["content"]["application/json"]["schema"]
    assert body["required"] == ["name"]
    assert set(body["properties"]) == {"name"}
    assert "created_by_user_id" in Input.model_json_schema()["required"]


def test_adapter_path_contracts_preserve_typed_parameters_and_are_repeatable():
    from uuid import UUID
    from fastapi import FastAPI, Request
    from woobe_api.http.shared.openapi_contracts import install_path_parameter_contracts

    app = FastAPI()

    @app.get("/adapter/{resource_id}")
    async def adapter(request: Request):
        return request.path_params

    @app.get("/typed/{resource_id}")
    async def typed(resource_id: UUID):
        return {"id": str(resource_id)}

    install_path_parameter_contracts(app)
    for _ in range(2):
        paths = app.openapi()["paths"]
        adapter_parameters = paths["/adapter/{resource_id}"]["get"]["parameters"]
        assert adapter_parameters == [{
            "name": "resource_id", "in": "path", "required": True,
            "schema": {"type": "string"},
        }]
        typed_parameters = paths["/typed/{resource_id}"]["get"]["parameters"]
        assert len(typed_parameters) == 1
        assert typed_parameters[0]["schema"]["format"] == "uuid"
