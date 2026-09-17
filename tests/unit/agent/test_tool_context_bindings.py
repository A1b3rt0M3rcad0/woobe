from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.tools_dtos import CreateToolInput
from modules.agent.application.tool_context_bindings import (
    ToolContextBindingError,
    apply_context_bindings,
)
from modules.agent.application.tool_converter import agent_tool_to_openai_definition
from modules.agent.domain.enums import ToolType


def binding(field: str) -> dict:
    return {"source": {"kind": "context", "field": field}}


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
        {"__mcp_remote_tool": "orders"},
        {"tenant_id": "tenant-1", "customer_id": "cus-1"},
    )
    assert result["tenant_id"] == "tenant-1"
    assert result["customer_id"] == "cus-1"


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
