from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.tools_dtos import CreateToolInput, UpdateToolInput
from modules.agent.application.interfaces.tool_runtime import MCP_REMOTE_TOOL_INPUT_KEY
from modules.agent.application.tool_context_bindings import (
    ToolContextBindingError,
    apply_context_bindings,
    collect_project_environment_binding_keys,
    merge_context_bindings_for_update,
)
from modules.agent.application.tool_converter import agent_tool_to_openai_definition
from modules.agent.domain.enums import ToolType


def binding(field: str) -> dict:
    return {"source": {"kind": "context", "field": field}}


def project_environment_binding(field: str) -> dict:
    return {"source": {"kind": "project_environment", "field": field}}


def test_context_binding_overrides_model_supplied_value() -> None:
    config = {"bindings": {"customer_id": binding("customer_id")}}
    result = apply_context_bindings(
        config,
        {"customer_id": "model-value", "query": "recent orders"},
        {"customer_id": "trusted-customer"},
    )
    assert result == {
        "customer_id": "trusted-customer",
        "query": "recent orders",
    }


def test_context_binding_fails_when_snapshot_value_is_unavailable() -> None:
    config = {"bindings": {"customer_id": binding("customer_id")}}
    with pytest.raises(ToolContextBindingError, match="customer_id"):
        apply_context_bindings(config, {}, {})


def test_project_environment_binding_overrides_model_supplied_value() -> None:
    config = {"bindings": {"api_key": project_environment_binding("API_KEY")}}
    result = apply_context_bindings(
        config,
        {"api_key": "model-forged-value", "query": "recent orders"},
        {},
        {"API_KEY": "runtime-secret"},
    )
    assert result == {
        "api_key": "runtime-secret",
        "query": "recent orders",
    }


def test_project_environment_binding_fails_when_value_is_unavailable() -> None:
    config = {"bindings": {"api_key": project_environment_binding("API_KEY")}}
    with pytest.raises(ToolContextBindingError, match="Project Environment key 'API_KEY'"):
        apply_context_bindings(config, {}, {}, {})


def test_project_environment_binding_rejects_invalid_key_name() -> None:
    config = {"bindings": {"api_key": project_environment_binding("API-KEY")}}
    with pytest.raises(
        ToolContextBindingError,
        match="valid Project Environment key",
    ):
        apply_context_bindings(config, {}, {}, {})


def test_collect_project_environment_binding_keys_includes_root_and_children() -> None:
    config = {
        "protocol": "http",
        "mode": "group",
        "base_url": "https://example.com",
        "bindings": {"tenant": project_environment_binding("TENANT_ID")},
        "routes": [
            {
                "id": "orders",
                "operation_id": "orders",
                "name": "Orders",
                "description": "List orders",
                "path": "/orders",
                "bindings": {"api_key": project_environment_binding("API_KEY")},
            }
        ],
    }

    assert collect_project_environment_binding_keys(config) == {"TENANT_ID", "API_KEY"}


def test_http_group_route_binding_is_selected_by_runtime_route() -> None:
    config = {
        "protocol": "http",
        "mode": "group",
        "base_url": "https://example.com",
        "bindings": {"tenant_id": binding("tenant_id")},
        "routes": [
            {
                "id": "orders",
                "operation_id": "orders",
                "name": "Orders",
                "description": "List orders",
                "path": "/orders/{{customer_id}}",
                "bindings": {"customer_id": binding("customer_id")},
            }
        ],
    }
    result = apply_context_bindings(
        config,
        {MCP_REMOTE_TOOL_INPUT_KEY: "orders"},
        {"tenant_id": "tenant-1", "customer_id": "cus-1"},
    )
    assert result["tenant_id"] == "tenant-1"
    assert result["customer_id"] == "cus-1"


def test_http_tool_config_accepts_project_environment_binding() -> None:
    created = CreateToolInput(
        project_id=uuid4(),
        type=ToolType.HTTP,
        name="Customer",
        config={
            "protocol": "http",
            "url": "https://example.com/customers",
            "bindings": {"api_key": project_environment_binding("API_KEY")},
        },
        input_schema={
            "type": "object",
            "properties": {"api_key": {"type": "string"}},
            "required": ["api_key"],
        },
    )
    assert created.config is not None
    assert created.config["bindings"]["api_key"] == project_environment_binding("API_KEY")


def test_http_tool_config_preserves_typed_bindings() -> None:
    created = CreateToolInput(
        project_id=uuid4(),
        type=ToolType.HTTP,
        name="Customer",
        config={
            "protocol": "http",
            "url": "https://example.com/customers/{{customer_id}}",
            "bindings": {"customer_id": binding("customer_id")},
        },
        input_schema={
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
        },
    )
    assert created.config is not None
    assert created.config["bindings"]["customer_id"] == binding("customer_id")


def test_http_update_keeps_omitted_bindings_distinct_from_explicit_empty() -> None:
    omitted = UpdateToolInput(
        type=ToolType.HTTP,
        config={
            "protocol": "http",
            "mode": "group",
            "base_url": "https://example.com",
            "routes": [
                {
                    "id": "orders",
                    "name": "Orders",
                    "description": "List orders",
                    "path": "/orders/{{customer_id}}",
                }
            ],
        },
    )
    assert omitted.config is not None
    assert "bindings" not in omitted.config
    assert "bindings" not in omitted.config["routes"][0]

    explicit = UpdateToolInput(
        type=ToolType.HTTP,
        config={
            "protocol": "http",
            "url": "https://example.com/customers/{{customer_id}}",
            "bindings": {},
        },
    )
    assert explicit.config is not None
    assert explicit.config["bindings"] == {}


def test_update_merge_preserves_omitted_root_and_child_bindings() -> None:
    existing = {
        "protocol": "http",
        "mode": "group",
        "base_url": "https://example.com",
        "bindings": {"tenant_id": binding("tenant_id")},
        "routes": [
            {
                "id": "orders",
                "operation_id": "orders",
                "name": "Orders",
                "bindings": {"customer_id": binding("customer_id")},
            }
        ],
    }
    candidate = {
        "protocol": "http",
        "mode": "group",
        "base_url": "https://api.example.com",
        "routes": [
            {
                "id": "orders",
                "operation_id": "orders",
                "name": "Orders v2",
            }
        ],
    }

    merged = merge_context_bindings_for_update(existing, candidate)
    assert merged["bindings"] == existing["bindings"]
    assert merged["routes"][0]["bindings"] == existing["routes"][0]["bindings"]

    cleared = merge_context_bindings_for_update(
        existing,
        {
            **candidate,
            "bindings": {},
            "routes": [{**candidate["routes"][0], "bindings": {}}],
        },
    )
    assert cleared["bindings"] == {}
    assert cleared["routes"][0]["bindings"] == {}


def test_update_merge_drops_legacy_route_binding_when_parameter_was_removed() -> None:
    existing = {
        "protocol": "http",
        "mode": "group",
        "base_url": "https://example.com",
        "routes": [
            {
                "id": "sum",
                "operation_id": "sum",
                "name": "Sum",
                "bindings": {"b": binding("age")},
            }
        ],
    }
    candidate = {
        "protocol": "http",
        "mode": "group",
        "base_url": "https://example.com",
        "routes": [
            {
                "id": "sum",
                "operation_id": "sum",
                "name": "Sum",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            }
        ],
    }

    merged = merge_context_bindings_for_update(existing, candidate)

    assert "bindings" not in merged["routes"][0]


def test_update_merge_keeps_only_bindings_for_still_declared_route_parameters() -> None:
    existing = {
        "protocol": "http",
        "mode": "group",
        "base_url": "https://example.com",
        "routes": [
            {
                "id": "search",
                "operation_id": "search",
                "name": "Search",
                "bindings": {
                    "customer_id": binding("customer_id"),
                    "removed": binding("removed"),
                },
            }
        ],
    }
    candidate = {
        "protocol": "http",
        "mode": "group",
        "base_url": "https://example.com",
        "routes": [
            {
                "id": "search",
                "operation_id": "search",
                "name": "Search",
                "input_schema": {
                    "type": "object",
                    "properties": {"customer_id": {"type": "string"}},
                    "required": ["customer_id"],
                    "additionalProperties": False,
                },
            }
        ],
    }

    merged = merge_context_bindings_for_update(existing, candidate)

    assert merged["routes"][0]["bindings"] == {
        "customer_id": binding("customer_id")
    }


def test_update_merge_preserves_omitted_mcp_discovered_tool_binding() -> None:
    existing = {
        "protocol": "mcp",
        "mode": "server",
        "server": {"url": "https://mcp.example.com"},
        "bindings": {"tenant_id": binding("tenant_id")},
        "discovered_tools": [
            {
                "name": "orders",
                "bindings": {"customer_id": binding("customer_id")},
            }
        ],
    }
    candidate = {
        "protocol": "mcp",
        "mode": "server",
        "server": {"url": "https://mcp.example.com/v2"},
        "discovered_tools": [{"name": "orders"}],
    }

    merged = merge_context_bindings_for_update(existing, candidate)
    assert merged["bindings"] == existing["bindings"]
    assert (
        merged["discovered_tools"][0]["bindings"]
        == existing["discovered_tools"][0]["bindings"]
    )


def test_bound_http_parameter_is_hidden_from_model_schema() -> None:
    tool = SimpleNamespace(
        id=uuid4(),
        type=ToolType.HTTP,
        name="Customer",
        description="Read customer",
        config={
            "protocol": "http",
            "url": "https://example.com/customers/{{customer_id}}?q={{query}}",
            "bindings": {"customer_id": binding("customer_id")},
        },
        input_schema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "query": {"type": "string"},
            },
            "required": ["customer_id", "query"],
        },
    )
    definition = agent_tool_to_openai_definition(tool)
    parameters = definition["function"]["parameters"]
    assert "customer_id" not in parameters["properties"]
    assert parameters["required"] == ["query"]


def test_bound_mcp_argument_is_hidden_from_model_schema() -> None:
    tool = SimpleNamespace(
        id=uuid4(),
        type=ToolType.MCP,
        name="Orders",
        description="Read orders",
        config={
            "protocol": "mcp",
            "server": {"url": "https://mcp.example.com"},
            "tool_name": "orders",
            "bindings": {"customer_id": binding("customer_id")},
            "discovered_input_schema": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["customer_id"],
            },
        },
        input_schema=None,
    )
    definition = agent_tool_to_openai_definition(tool)
    parameters = definition["function"]["parameters"]
    assert "customer_id" not in parameters["properties"]
    assert parameters["required"] == []
