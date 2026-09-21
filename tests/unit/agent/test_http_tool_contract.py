from __future__ import annotations

import json

import pytest

from modules.agent.application.http_tool_contract import (
    HttpToolContractError,
    compile_http_tool_group_contract,
    compile_http_tool_contract,
)
from modules.agent.infra.adapters.http_tool_renderer import render_http_tool_request


def mathjs_config() -> dict:
    return {
        "protocol": "http",
        "method": "POST",
        "url": "https://api.mathjs.org/v4/",
        "headers": [{"key": "Content-Type", "value": "application/json"}],
        "body": '{"expr":"{{a}} + {{b}}"}',
    }


def test_compiler_recovers_parameters_from_body_when_saved_schema_is_empty() -> None:
    contract = compile_http_tool_contract(
        mathjs_config(),
        {"type": "object", "properties": {}, "required": []},
    )

    assert set(contract.input_schema["properties"]) == {"a", "b"}
    assert contract.input_schema["required"] == ["a", "b"]
    assert contract.contract_hash


def test_compiler_drops_stale_declared_parameters_not_used_by_template() -> None:
    contract = compile_http_tool_contract(
        {
            "protocol": "http",
            "method": "GET",
            "url": "https://api.example.com/search?q={{b}}&age={{external_context.age}}",
            "headers": [],
        },
        {
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
            "required": ["a", "b"],
        },
    )

    assert contract.parameter_names == ("b",)
    assert contract.input_schema["properties"] == {"b": {"type": "integer"}}
    assert contract.input_schema["required"] == ["b"]


def test_runtime_templates_never_become_model_inputs() -> None:
    contract = compile_http_tool_contract(
        {
            "protocol": "http",
            "method": "GET",
            "url": (
                "https://api.example.com/{{external_context.customer_id}}"
                "?token={{project_env.API_KEY}}&query={{query}}"
            ),
            "headers": [],
        }
    )

    assert contract.parameter_names == ("query",)
    assert set(contract.input_schema["properties"]) == {"query"}
    assert contract.input_schema["required"] == ["query"]


def test_renderer_builds_valid_json_body_with_real_arguments() -> None:
    contract = compile_http_tool_contract(mathjs_config())

    url, headers, body = render_http_tool_request(
        contract,
        {"a": 20, "b": 25},
        {"Content-Type": "application/json"},
    )

    assert url == "https://api.mathjs.org/v4/"
    assert headers == {"Content-Type": "application/json"}
    assert json.loads(body or "") == {"expr": "20 + 25"}


def test_renderer_interpolates_headers_and_encodes_url_values() -> None:
    config = {
        "method": "GET",
        "url": "https://api.example.com/search?q={{query}}",
        "headers": [{"key": "X-Tenant", "value": "{{tenant}}"}],
    }
    contract = compile_http_tool_contract(config)

    url, headers, body = render_http_tool_request(
        contract,
        {"query": "A+B / test", "tenant": "tenant-1"},
        {"X-Tenant": "{{tenant}}"},
    )

    assert url == "https://api.example.com/search?q=A%2BB%20%2F%20test"
    assert headers == {"X-Tenant": "tenant-1"}
    assert body is None


def test_renderer_rejects_missing_required_parameters_before_http_request() -> None:
    contract = compile_http_tool_contract(mathjs_config())

    with pytest.raises(HttpToolContractError) as exc_info:
        render_http_tool_request(
            contract,
            {},
            {"Content-Type": "application/json"},
        )

    assert exc_info.value.code == "HTTP_TOOL_PARAMETER_MISSING"
    assert exc_info.value.missing == ["a", "b"]


def test_compiler_rejects_single_brace_placeholders() -> None:
    config = {
        "method": "POST",
        "url": "https://api.example.com",
        "headers": [{"key": "Content-Type", "value": "application/json"}],
        "body": '{"expr":"{a} + {b}"}',
    }

    with pytest.raises(HttpToolContractError) as exc_info:
        compile_http_tool_contract(config)

    assert exc_info.value.code == "HTTP_TOOL_TEMPLATE_INVALID"


def test_group_contract_accepts_runtime_template_base_url() -> None:
    contract = compile_http_tool_group_contract(
        {
            "protocol": "http",
            "mode": "group",
            "base_url": "{{project_env.API_URL}}",
            "headers": [],
            "routes": [
                {
                    "id": "route-1",
                    "name": "Create customer",
                    "description": "Create one customer.",
                    "method": "POST",
                    "path": "/customers",
                    "headers": [],
                    "risk_level": "low",
                    "status": "active",
                    "default_permission": "allow",
                }
            ],
        }
    )

    assert contract.config["base_url"] == "{{project_env.API_URL}}"
