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
