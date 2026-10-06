"""Contracts exported by the immutable Go CLI, independent of server routing."""

import json
from pathlib import Path
import re

import pytest

FIXTURE = Path(__file__).with_name("fixtures") / "woobe_cli_operations.json"
CONTRACT = json.loads(FIXTURE.read_text())
OPERATIONS = CONTRACT["operations"]


@pytest.fixture(scope="module")
def schema():
    from main import create_app

    return create_app().openapi()


def shape(path):
    # The CLI accepts renamed placeholders, but refuses ambiguous templates.
    return re.sub(r"\{[^}]+\}", "{}", path)


@pytest.mark.parametrize("command", OPERATIONS, ids=lambda op: op["command"])
def test_every_pinned_cli_http_command_has_an_unambiguous_server_contract(
    schema, command
):
    candidates = [
        path
        for path, item in schema["paths"].items()
        if shape(path) == shape(command["path"]) and command["method"].lower() in item
    ]
    assert len(candidates) == 1, command
    path = candidates[0]
    operation = schema["paths"][path][command["method"].lower()]
    parameters = schema["paths"][path].get("parameters", []) + operation.get(
        "parameters", []
    )
    identities = [(parameter["name"], parameter["in"]) for parameter in parameters]
    assert len(identities) == len(set(identities)), command
    for name in re.findall(r"\{([^}]+)\}", path):
        parameter = next(
            item for item in parameters if (item["name"], item["in"]) == (name, "path")
        )
        assert parameter["required"] is True
        assert parameter.get("schema"), command
    if command["body_required"]:
        assert operation["requestBody"]["content"]["application/json"]["schema"], (
            command
        )


def test_server_derived_api_key_actors_are_not_client_input(schema):
    for path, method in [
        ("/core/projects/{project_id}/api-keys", "post"),
        ("/core/projects/{project_id}/runtime-keys", "post"),
        ("/core/projects/{project_id}/api-keys/{api_key_id}", "patch"),
        ("/core/projects/{project_id}/api-keys/{api_key_id}/rotate", "post"),
    ]:
        body = schema["paths"][path][method]["requestBody"]["content"][
            "application/json"
        ]["schema"]
        assert not any(
            name.startswith(("created_by_", "updated_by_", "rotated_by_"))
            for name in body["properties"]
        )
        assert "project_id" not in body["properties"]
        assert "api_key_id" not in body["properties"]
