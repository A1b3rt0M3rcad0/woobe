import inspect

from fastapi import FastAPI

from modules.core.entrypoint import CreateProjectInput
from woobe_api.http.core.routes import create_project, router


def test_project_creation_advertises_the_authoritative_input_schema() -> None:
    app = FastAPI()
    app.include_router(router)
    operation = app.openapi()["paths"]["/core/projects"]["post"]
    body = operation["requestBody"]
    assert body["required"] is True
    schema = body["content"]["application/json"]["schema"]
    assert schema == CreateProjectInput.model_json_schema(mode="validation")
    assert schema["properties"]["workspace_id"]["format"] == "uuid"
    assert set(schema["required"]) == {"workspace_id", "name", "slug"}


def test_project_schema_advertisement_preserves_explicit_request_dispatch() -> None:
    # DTO parsing stays within create_project_atomically. Advertising the schema
    # must not add FastAPI body coercion ahead of the existing authority path.
    assert list(inspect.signature(create_project).parameters) == ["request"]
