from __future__ import annotations

import json
from dataclasses import dataclass, field
from uuid import uuid4

import pytest

from modules.agent.application.http_tool_contract import (
    HttpToolContractError,
    compile_http_group_route_contract,
    compile_http_tool_group_contract,
)
from modules.agent.application.interfaces.ports import ExecutionResult, ToolExecutionPort
from modules.agent.application.tool_converter import (
    MCP_PROVIDER_ROUTE_SEPARATOR,
    agent_tools_to_openai_definitions_and_mapping,
)
from modules.agent.application.tool_release_snapshots import tool_with_permission_overrides
from modules.agent.application.tool_runtime import (
    ERROR_HTTP_ROUTE_REQUIRES_POLICY,
    MCP_REMOTE_TOOL_INPUT_KEY,
    HttpToolRuntime,
)
from modules.agent.domain.entities import Tool
from modules.agent.domain.enums import RiskLevel, ToolStatus, ToolType


class FakeExecutor(ToolExecutionPort):
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def execute(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_ms: int = 30000,
    ) -> ExecutionResult:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers or {},
                "body": body,
                "timeout_ms": timeout_ms,
            }
        )
        return ExecutionResult(
            success=True,
            status_code=200,
            output={"body": {"ok": True}},
            duration_ms=2,
        )


@dataclass
class FakeTool:
    config: dict
    id: object = field(default_factory=uuid4)
    project_id: object = field(default_factory=uuid4)
    type: ToolType = ToolType.HTTP
    name: str = "Public Data"
    description: str = "Search public employee and salary data."
    input_schema: dict | None = None
    timeout_ms: int = 30000


def group_config(*, permission: str = "allow") -> dict:
    return {
        "protocol": "http",
        "mode": "group",
        "schema_version": 2,
        "base_url": "https://api.example.com/v1",
        "headers": [
            {"key": "X-Shared", "value": "shared"},
        ],
        "timeout_ms": 30000,
        "routes": [
            {
                "id": "route-search",
                "operation_id": "search_employee",
                "name": "Search employee",
                "description": "Searches a public employee by name.",
                "method": "POST",
                "path": "/employees/search",
                "headers": [{"key": "X-Route", "value": "route"}],
                "body": '{"name":"{{name}}","limit":{{limit}}}',
                "variables": {"limit": 10},
                "risk_level": "low",
                "status": "active",
                "default_permission": permission,
            },
            {
                "id": "route-private",
                "operation_id": "private_operation",
                "name": "Private operation",
                "description": "A route that is not exposed to the Agent.",
                "method": "GET",
                "path": "/private",
                "risk_level": "high",
                "status": "active",
                "default_permission": "deny",
            },
        ],
    }


def test_group_contract_compiles_each_route_and_keeps_shared_base_url() -> None:
    compiled = compile_http_tool_group_contract(group_config())

    assert compiled.version == 2
    assert compiled.config["mode"] == "group"
    assert compiled.config["base_url"] == "https://api.example.com/v1"
    assert set(compiled.route_contracts) == {"route-search", "route-private"}
    search = compiled.config["routes"][0]
    assert search["input_schema"]["required"] == ["name"]
    assert search["input_schema"]["properties"]["limit"]["type"] == "string"
    assert search["contract_hash"] == compiled.route_contracts["route-search"].contract_hash


def test_group_contract_generates_stable_unique_operation_ids() -> None:
    config = group_config()
    config["routes"][0].pop("operation_id")
    config["routes"][0]["name"] = "Consultar remuneração"
    config["routes"][1].pop("operation_id")
    config["routes"][1]["name"] = "Consultar remuneração"

    compiled = compile_http_tool_group_contract(config)

    assert compiled.config["routes"][0]["operation_id"] == "consultar_remuneracao"
    assert compiled.config["routes"][1]["operation_id"] == "consultar_remuneracao_2"


def test_group_contract_preserves_explicit_operation_id() -> None:
    config = group_config()
    config["routes"][0]["name"] = "Find public employees"

    compiled = compile_http_tool_group_contract(config)

    assert compiled.config["routes"][0]["operation_id"] == "search_employee"


def test_group_contract_rejects_duplicate_operation_ids() -> None:
    config = group_config()
    config["routes"][1]["operation_id"] = "search_employee"

    with pytest.raises(HttpToolContractError) as exc:
        compile_http_tool_group_contract(config)

    assert exc.value.code == "HTTP_TOOL_OPERATION_ID_DUPLICATE"


def test_route_headers_override_shared_headers_case_insensitively() -> None:
    config = group_config()
    config["headers"] = [
        {"key": "Authorization", "value": "Bearer shared"},
        {"key": "Accept", "value": "application/json"},
    ]
    config["routes"][0]["headers"] = [
        {"key": "authorization", "value": "Bearer route", "mode": "set"},
    ]

    compiled = compile_http_tool_group_contract(config)
    route_contract = compile_http_group_route_contract(compiled.config, "route-search")
    headers = {item["key"].lower(): item["value"] for item in route_contract.config["headers"]}

    assert headers["authorization"] == "Bearer route"
    assert headers["accept"] == "application/json"


def test_route_can_remove_inherited_header() -> None:
    config = group_config()
    config["headers"] = [
        {"key": "Authorization", "value": "Bearer shared"},
        {"key": "Accept", "value": "application/json"},
    ]
    config["routes"][0]["headers"] = [
        {"key": "Authorization", "mode": "remove"},
        {"key": "X-Route", "value": "route"},
    ]

    compiled = compile_http_tool_group_contract(config)
    route_contract = compile_http_group_route_contract(compiled.config, "route-search")
    headers = {item["key"].lower(): item.get("value") for item in route_contract.config["headers"]}

    assert "authorization" not in headers
    assert headers["accept"] == "application/json"
    assert headers["x-route"] == "route"


def test_group_contract_rejects_duplicate_headers_in_same_layer() -> None:
    config = group_config()
    config["headers"] = [
        {"key": "Accept", "value": "application/json"},
        {"key": "accept", "value": "text/plain"},
    ]

    with pytest.raises(HttpToolContractError) as exc:
        compile_http_tool_group_contract(config)

    assert exc.value.code == "HTTP_TOOL_HEADER_DUPLICATE"


def test_group_contract_rejects_reserved_headers() -> None:
    config = group_config()
    config["routes"][0]["headers"] = [{"key": "Content-Length", "value": "100"}]

    with pytest.raises(HttpToolContractError) as exc:
        compile_http_tool_group_contract(config)

    assert exc.value.code == "HTTP_TOOL_HEADER_RESERVED"


def test_shared_headers_cannot_use_remove_mode() -> None:
    config = group_config()
    config["headers"] = [{"key": "Authorization", "mode": "remove"}]

    with pytest.raises(HttpToolContractError) as exc:
        compile_http_tool_group_contract(config)

    assert exc.value.code == "HTTP_TOOL_HEADER_REMOVE_INVALID"


def test_converter_exposes_only_allowed_routes() -> None:
    compiled = compile_http_tool_group_contract(group_config())
    tool = FakeTool(config=compiled.config)

    definitions, mapping = agent_tools_to_openai_definitions_and_mapping([tool])

    names = [item.get("function", {}).get("name") for item in definitions]
    assert "public_data_search_employee" in names
    assert "public_data_private_operation" not in names
    assert mapping["public_data_search_employee"] == f"{tool.id}{MCP_PROVIDER_ROUTE_SEPARATOR}route-search"


@pytest.mark.asyncio
async def test_runtime_executes_selected_route_with_shared_and_route_headers() -> None:
    compiled = compile_http_tool_group_contract(group_config())
    executor = FakeExecutor()
    runtime = HttpToolRuntime(executor)
    tool = FakeTool(config=compiled.config)

    result = await runtime.execute(
        tool,
        {
            MCP_REMOTE_TOOL_INPUT_KEY: "route-search",
            "name": "Maria Silva",
        },
    )

    assert result.success is True
    assert len(executor.calls) == 1
    call = executor.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://api.example.com/v1/employees/search"
    assert call["headers"]["X-Shared"] == "shared"
    assert call["headers"]["X-Route"] == "route"
    assert json.loads(call["body"]) == {"name": "Maria Silva", "limit": 10}
    assert result.output["http_route_id"] == "route-search"
    assert result.output["http_operation_id"] == "search_employee"


@pytest.mark.asyncio
async def test_runtime_uses_effective_headers_after_override_and_removal() -> None:
    config = group_config()
    config["headers"] = [
        {"key": "Authorization", "value": "Bearer shared"},
        {"key": "Accept", "value": "application/json"},
    ]
    config["routes"][0]["headers"] = [
        {"key": "authorization", "value": "Bearer route"},
        {"key": "Accept", "mode": "remove"},
    ]
    compiled = compile_http_tool_group_contract(config)
    executor = FakeExecutor()
    runtime = HttpToolRuntime(executor)

    result = await runtime.execute(
        FakeTool(config=compiled.config),
        {MCP_REMOTE_TOOL_INPUT_KEY: "route-search", "name": "Maria"},
    )

    assert result.success is True
    headers = {key.lower(): value for key, value in executor.calls[0]["headers"].items()}
    assert headers["authorization"] == "Bearer route"
    assert "accept" not in headers


@pytest.mark.asyncio
async def test_runtime_blocks_route_that_still_requires_permission() -> None:
    compiled = compile_http_tool_group_contract(group_config(permission="review"))
    executor = FakeExecutor()
    runtime = HttpToolRuntime(executor)

    result = await runtime.execute(
        FakeTool(config=compiled.config),
        {MCP_REMOTE_TOOL_INPUT_KEY: "route-search", "name": "Maria"},
    )

    assert result.success is False
    assert result.output["error_code"] == ERROR_HTTP_ROUTE_REQUIRES_POLICY
    assert executor.calls == []


def test_agent_permission_override_is_applied_to_http_route() -> None:
    compiled = compile_http_tool_group_contract(group_config(permission="review"))
    tool = Tool(
        id=uuid4(),
        project_id=uuid4(),
        name="Public Data",
        description="Public data API",
        type=ToolType.HTTP,
        config=compiled.config,
        risk_level=RiskLevel.LOW,
        status=ToolStatus.ACTIVE,
    )

    effective = tool_with_permission_overrides(
        tool,
        {"route-search": {"mode": "allow", "risk_level": "low"}},
    )

    assert effective.config["routes"][0]["permission"]["mode"] == "allow"
    assert "permission" not in tool.config["routes"][0]
