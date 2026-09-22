from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.tools_dtos import UpdateToolInput
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyRequest
from modules.agent.application.interfaces.ports import ExecutionResult, ToolExecutionPort
from modules.agent.application.interfaces.tool_runtime import MCP_REMOTE_TOOL_INPUT_KEY
from modules.agent.application.tool_converter import (
    agent_tools_to_openai_definitions_and_mapping,
)
from modules.agent.application.tool_release_snapshots import (
    tool_from_release_snapshot,
    tool_to_release_snapshot,
    tool_with_permission_overrides,
)
from modules.agent.domain.entities import Agent, Tool
from modules.agent.domain.enums import RiskLevel, ToolStatus, ToolType
from modules.agent.infra.adapters.tool_runtime import HttpToolRuntime
from modules.agent.infra.execution import agent_tool_runtime_gateway as gateway_module
from modules.agent.infra.execution.capabilities.preparation import prepare_execution
from modules.agent.infra.execution.agent_tool_runtime_gateway import AgentToolRuntimeGateway
from modules.agent.infra.execution.release_runtime_resolver import ReleaseRuntimeResolver
from modules.agent.infra.execution.runtime_preparation import prepare_tool_state
from shared.infra.crypto import encrypt_secret
from shared.project_environment import PreparedProjectEnvironmentValue


class _ToolRepo:
    def __init__(self, tool: Tool) -> None:
        self.tool = tool
        self.read_ids = []

    async def get_by_id(self, tool_id):
        self.read_ids.append(tool_id)
        return self.tool


class _HttpExecutor(ToolExecutionPort):
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
            output={"body": 25},
            duration_ms=1,
        )


def _stale_config() -> dict:
    return {
        "protocol": "http",
        "mode": "group",
        "schema_version": 2,
        "base_url": "https://api.mathjs.org",
        "headers": [],
        "routes": [
            {
                "id": "route-sum",
                "operation_id": "sum_2_numbers",
                "name": "Sum 2 numbers",
                "description": "Sums two numbers.",
                "method": "GET",
                "path": "/v4/?expr={{external_context.age}}%2B{{b}}",
                "headers": [],
                "bindings": {},
                "input_schema": {
                    "type": "object",
                    "properties": {"b": {"type": "string"}},
                    "required": ["b"],
                    "additionalProperties": False,
                },
                "risk_level": "low",
                "status": "active",
                "default_permission": "allow",
            }
        ],
    }


def _runtime_only_config() -> dict:
    return {
        "protocol": "http",
        "mode": "group",
        "schema_version": 2,
        "base_url": "https://api.mathjs.org",
        "headers": [],
        "routes": [
            {
                "id": "route-sum",
                "operation_id": "sum_2_numbers",
                "name": "Sum 2 numbers",
                "description": "Sums External Context age with a Project Environment value.",
                "method": "GET",
                "path": (
                    "/v4/?expr={{external_context.age}}"
                    "%2B{{project_env.MOCKED_NUMBER}}"
                ),
                "headers": [],
                # Simulate persisted historical noise. The current template is the
                # authority and must compile this stale field away.
                "input_schema": {
                    "type": "object",
                    "properties": {"b": {"type": "string"}},
                    "required": ["b"],
                    "additionalProperties": False,
                },
                "bindings": {},
                "risk_level": "low",
                "status": "active",
                "default_permission": "allow",
            }
        ],
    }


def _mixed_runtime_config() -> dict:
    return {
        "protocol": "http",
        "mode": "group",
        "schema_version": 2,
        "base_url": "{{project_env.API_URL}}",
        "headers": [],
        "routes": [
            {
                "id": "route-orders",
                "operation_id": "list_orders",
                "name": "List orders",
                "description": "Lists orders for the runtime customer.",
                "method": "POST",
                "path": (
                    "/customers/{{external_context.customer_id}}"
                    "?tenant={{project_env.TENANT_ID}}"
                ),
                "headers": [
                    {
                        "key": "Authorization",
                        "value": "Bearer {{project_env.API_KEY}}",
                    }
                ],
                "body": (
                    '{"query":"{{query}}",'
                    '"customer":"{{external_context.customer_id}}"}'
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "removed": {"type": "string"},
                    },
                    "required": ["query", "removed"],
                    "additionalProperties": False,
                },
                "bindings": {},
                "risk_level": "low",
                "status": "active",
                "default_permission": "allow",
            }
        ],
    }


def _tool(*, config: dict, tool_id=None, project_id=None) -> Tool:
    return Tool(
        id=tool_id or uuid4(),
        project_id=project_id or uuid4(),
        name="api.mathjs.org",
        description="Math API",
        type=ToolType.HTTP,
        config=deepcopy(config),
        input_schema={
            "type": "object",
            "properties": {"b": {"type": "string"}},
            "required": ["b"],
            "additionalProperties": False,
        },
        risk_level=RiskLevel.LOW,
        status=ToolStatus.ACTIVE,
    )


def _agent(*, project_id, tool_id, snapshot) -> Agent:
    return Agent(
        id=uuid4(),
        project_id=project_id,
        name="runtime-agent",
        model="test-model",
        settings={
            "runtime_config": {
                "tools": {
                    "tool_ids": [str(tool_id)],
                    "snapshots": [snapshot],
                }
            }
        },
    )


def test_update_dto_compiles_removed_agent_input_out_of_http_group() -> None:
    dto = UpdateToolInput(
        type=ToolType.HTTP,
        config=_runtime_only_config(),
    )

    route = dto.config["routes"][0]
    assert route["path"].endswith(
        "{{external_context.age}}%2B{{project_env.MOCKED_NUMBER}}"
    )
    assert route["input_schema"] == {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }


@pytest.mark.asyncio
async def test_draft_acceptance_reads_live_tool_instead_of_stale_release_snapshot() -> None:
    project_id = uuid4()
    tool_id = uuid4()
    stale = _tool(config=_stale_config(), tool_id=tool_id, project_id=project_id)
    live = _tool(config=_runtime_only_config(), tool_id=tool_id, project_id=project_id)
    snapshot = tool_to_release_snapshot(stale)
    repo = _ToolRepo(live)
    repositories = SimpleNamespace(
        tools=repo,
        tool_secrets=SimpleNamespace(),
    )

    tools, _secrets = await prepare_tool_state(
        repositories,
        agent=_agent(project_id=project_id, tool_id=tool_id, snapshot=snapshot),
        tool_from_snapshot=tool_from_release_snapshot,
        tool_with_permissions=tool_with_permission_overrides,
        prefer_live_tools=True,
    )

    assert repo.read_ids == [tool_id]
    assert tools[0].config["routes"][0]["path"].endswith(
        "{{external_context.age}}%2B{{project_env.MOCKED_NUMBER}}"
    )

    definitions, _mapping = agent_tools_to_openai_definitions_and_mapping(tools)
    assert definitions[0]["function"]["parameters"] == {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }


@pytest.mark.asyncio
async def test_release_acceptance_keeps_stale_snapshot_immutable_when_live_tool_changes() -> None:
    project_id = uuid4()
    tool_id = uuid4()
    stale = _tool(config=_stale_config(), tool_id=tool_id, project_id=project_id)
    live = _tool(config=_runtime_only_config(), tool_id=tool_id, project_id=project_id)
    snapshot = tool_to_release_snapshot(stale)
    repo = _ToolRepo(live)
    repositories = SimpleNamespace(
        tools=repo,
        tool_secrets=SimpleNamespace(),
    )

    tools, _secrets = await prepare_tool_state(
        repositories,
        agent=_agent(project_id=project_id, tool_id=tool_id, snapshot=snapshot),
        tool_from_snapshot=tool_from_release_snapshot,
        tool_with_permissions=tool_with_permission_overrides,
        prefer_live_tools=False,
    )

    assert repo.read_ids == []
    definitions, _mapping = agent_tools_to_openai_definitions_and_mapping(tools)
    assert set(definitions[0]["function"]["parameters"]["properties"]) == {"b"}


@pytest.mark.asyncio
async def test_existing_playground_session_rebuilds_tool_definition_from_live_acceptance_state() -> None:
    project_id = uuid4()
    tool_id = uuid4()
    stale = _tool(config=_stale_config(), tool_id=tool_id, project_id=project_id)
    live = _tool(config=_runtime_only_config(), tool_id=tool_id, project_id=project_id)
    snapshot = tool_to_release_snapshot(stale)
    agent = _agent(project_id=project_id, tool_id=tool_id, snapshot=snapshot)
    repo = _ToolRepo(live)
    repositories = SimpleNamespace(tools=repo, tool_secrets=SimpleNamespace())

    accepted_tools, _secrets = await prepare_tool_state(
        repositories,
        agent=agent,
        tool_from_snapshot=tool_from_release_snapshot,
        tool_with_permissions=tool_with_permission_overrides,
        prefer_live_tools=True,
    )

    context = new_execution_context()
    context.execution_context = "playground"
    context.session_id = uuid4()
    context.prepared_tools = {str(tool.id): tool for tool in accepted_tools}

    async def _read_runtime_tools(tool_ids):
        return [context.prepared_tools[str(tool_id)] for tool_id in tool_ids]

    resolver = ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver)
    resolver.configure_runtime_tool_reader(_read_runtime_tools)
    prepared = (
        agent,
        SimpleNamespace(id=context.session_id),
        uuid4(),
        "api-key",
        None,
        {},
        False,
        [],
        {},
        False,
        [],
        [],
        [],
    )

    token = current_execution.set(context)
    try:
        resolved = await resolver._apply_runtime_tool_selection(prepared)
    finally:
        current_execution.reset(token)

    assert context.tool_metadata["source"] == "draft_live"
    assert resolved[7][0]["function"]["parameters"] == {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }
    frozen = context.tool_snapshots[str(tool_id)]
    assert "project_env.MOCKED_NUMBER" in frozen["config"]["routes"][0]["path"]
    frozen_schema = frozen["config"]["routes"][0]["input_schema"]
    assert "b" not in frozen_schema["properties"]
    assert "b" not in frozen_schema["required"]


@pytest.mark.asyncio
async def test_draft_rerun_keeps_historical_tool_snapshot_instead_of_live_tool() -> None:
    project_id = uuid4()
    tool_id = uuid4()
    stale = _tool(config=_stale_config(), tool_id=tool_id, project_id=project_id)
    live = _tool(config=_runtime_only_config(), tool_id=tool_id, project_id=project_id)
    snapshot = tool_to_release_snapshot(stale)
    agent = _agent(project_id=project_id, tool_id=tool_id, snapshot=snapshot)

    context = new_execution_context()
    context.execution_context = "playground"
    context.prepared_tools = {str(tool_id): live}

    async def _must_not_read_live(_tool_ids):
        raise AssertionError("Draft rerun must reproduce the historical Tool snapshot")

    resolver = ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver)
    resolver.configure_runtime_tool_reader(_must_not_read_live)
    prepared = (
        agent,
        None,
        uuid4(),
        "api-key",
        None,
        {},
        False,
        [],
        {},
        False,
        [],
        [],
        [],
    )
    input_dto = SimpleNamespace(
        execution_context="playground",
        metadata={"source": "rerun", "rerun_of_run_id": str(uuid4())},
    )

    token = current_execution.set(context)
    try:
        resolved = await resolver._apply_runtime_tool_selection(
            prepared,
            input_dto=input_dto,
        )
    finally:
        current_execution.reset(token)

    assert context.tool_metadata["source"] == "release_snapshot"
    assert set(resolved[7][0]["function"]["parameters"]["properties"]) == {"b"}


def test_network_runtime_metadata_disables_draft_live_tools_before_network_ids_exist() -> None:
    context = new_execution_context()
    context.execution_context = "playground"
    input_dto = SimpleNamespace(
        execution_context="playground",
        metadata={"source": "network_runtime"},
    )

    token = current_execution.set(context)
    try:
        assert ReleaseRuntimeResolver._prefer_live_tools(input_dto) is False
    finally:
        current_execution.reset(token)


@pytest.mark.asyncio
async def test_network_playground_context_keeps_release_tool_snapshot() -> None:
    project_id = uuid4()
    tool_id = uuid4()
    stale = _tool(config=_stale_config(), tool_id=tool_id, project_id=project_id)
    live = _tool(config=_runtime_only_config(), tool_id=tool_id, project_id=project_id)
    snapshot = tool_to_release_snapshot(stale)
    agent = _agent(project_id=project_id, tool_id=tool_id, snapshot=snapshot)

    context = new_execution_context()
    context.execution_context = "playground"
    context.network_execution_id = uuid4()
    context.prepared_tools = {str(tool_id): live}

    async def _must_not_read_live(_tool_ids):
        raise AssertionError("Network execution must keep the frozen Tool snapshot")

    resolver = ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver)
    resolver.configure_runtime_tool_reader(_must_not_read_live)
    prepared = (
        agent,
        None,
        uuid4(),
        "api-key",
        None,
        {},
        False,
        [],
        {},
        False,
        [],
        [],
        [],
    )

    token = current_execution.set(context)
    try:
        resolved = await resolver._apply_runtime_tool_selection(prepared)
    finally:
        current_execution.reset(token)

    assert context.tool_metadata["source"] == "release_snapshot"
    assert set(resolved[7][0]["function"]["parameters"]["properties"]) == {"b"}


def test_provider_bind_tools_receives_no_removed_agent_argument() -> None:
    project_id = uuid4()
    live = _tool(config=_runtime_only_config(), project_id=project_id)
    definitions, mapping = agent_tools_to_openai_definitions_and_mapping([live])

    class _RecordingModel:
        def __init__(self) -> None:
            self.bound_tools = None

        def bind_tools(self, tools, *, tool_choice):
            assert tool_choice == "auto"
            self.bound_tools = deepcopy(tools)
            return self

    class _Factory:
        def __init__(self) -> None:
            self.model = _RecordingModel()

        def create_chat_model(self, **_kwargs):
            return self.model

    factory = _Factory()
    request = ExecutionStrategyRequest(
        llm_factory=factory,
        execute_single_tool=lambda *_args: None,  # type: ignore[arg-type]
        clean_json_answer=lambda value: value,
        agent=SimpleNamespace(
            provider="openai",
            model="test-model",
            temperature=0.2,
            max_output_tokens=256,
            settings={},
        ),
        api_key="test",
        base_url=None,
        response_format={},
        json_enabled=False,
        has_tools=True,
        agent_tools=definitions,
        tool_name_to_id=mapping,
        messages=[],
        context_assembler=None,
    )

    prepare_execution(request)

    assert factory.model.bound_tools is not None
    parameters = factory.model.bound_tools[0]["function"]["parameters"]
    assert parameters == {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }
    assert "b" not in parameters["properties"]
    assert "b" not in parameters["required"]


@pytest.mark.asyncio
async def test_same_session_run_uses_runtime_only_values_and_model_supplies_nothing(
    monkeypatch,
) -> None:
    project_id = uuid4()
    tool_id = uuid4()
    live = _tool(config=_runtime_only_config(), tool_id=tool_id, project_id=project_id)
    executor = _HttpExecutor()
    runtime = HttpToolRuntime(executor)

    class _Registry:
        async def execute(self, runtime_tool, input_data):
            return await runtime.execute(runtime_tool, input_data)

    monkeypatch.setattr(
        gateway_module,
        "build_tool_runtime_registry",
        lambda **_kwargs: _Registry(),
    )
    monkeypatch.setattr(
        gateway_module,
        "record_tool_provider_latency",
        lambda _duration_ms: None,
    )

    context = new_execution_context()
    context.execution_context = "playground"
    context.session_id = uuid4()
    context.prepared_tools = {str(tool_id): live}
    context.tool_snapshots = {str(tool_id): tool_to_release_snapshot(live)}
    context.external_context_snapshot = {"age": 18}
    context.prepared_project_environment = {
        "MOCKED_NUMBER": PreparedProjectEnvironmentValue(
            kind="value",
            stored_value="7",
        )
    }

    token = current_execution.set(context)
    try:
        gateway = AgentToolRuntimeGateway(
            None,
            SimpleNamespace(encryption_key="test-key"),
            executor=executor,
        )
        result = await gateway.execute_tool(
            tool_id,
            {MCP_REMOTE_TOOL_INPUT_KEY: "route-sum"},
        )
    finally:
        current_execution.reset(token)

    assert result["success"] is True
    assert executor.calls == [
        {
            "method": "GET",
            "url": "https://api.mathjs.org/v4/?expr=18%2B7",
            "headers": {},
            "body": None,
            "timeout_ms": 30000,
        }
    ]


@pytest.mark.asyncio
async def test_mixed_runtime_namespaces_leave_only_real_agent_input_and_resolve_request(
    monkeypatch,
) -> None:
    project_id = uuid4()
    tool_id = uuid4()
    live = _tool(config=_mixed_runtime_config(), tool_id=tool_id, project_id=project_id)

    definitions, _mapping = agent_tools_to_openai_definitions_and_mapping([live])
    parameters = definitions[0]["function"]["parameters"]
    assert parameters == {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
        "additionalProperties": False,
    }
    assert "customer_id" not in str(parameters)
    assert "API_URL" not in str(parameters)
    assert "API_KEY" not in str(parameters)
    assert "TENANT_ID" not in str(parameters)
    assert "removed" not in str(parameters)

    executor = _HttpExecutor()
    runtime = HttpToolRuntime(executor)

    class _Registry:
        async def execute(self, runtime_tool, input_data):
            return await runtime.execute(runtime_tool, input_data)

    monkeypatch.setattr(
        gateway_module,
        "build_tool_runtime_registry",
        lambda **_kwargs: _Registry(),
    )
    monkeypatch.setattr(
        gateway_module,
        "record_tool_provider_latency",
        lambda _duration_ms: None,
    )

    context = new_execution_context()
    context.execution_context = "playground"
    context.prepared_tools = {str(tool_id): live}
    context.tool_snapshots = {str(tool_id): tool_to_release_snapshot(live)}
    context.external_context_snapshot = {"customer_id": "cus-1"}
    context.prepared_project_environment = {
        "API_URL": PreparedProjectEnvironmentValue(
            kind="value",
            stored_value="https://api.example.com",
        ),
        "TENANT_ID": PreparedProjectEnvironmentValue(
            kind="value",
            stored_value="tenant-7",
        ),
        "API_KEY": PreparedProjectEnvironmentValue(
            kind="secret",
            stored_value=encrypt_secret("runtime-secret", "test-key"),
        ),
    }

    token = current_execution.set(context)
    try:
        gateway = AgentToolRuntimeGateway(
            None,
            SimpleNamespace(encryption_key="test-key"),
            executor=executor,
        )
        result = await gateway.execute_tool(
            tool_id,
            {
                MCP_REMOTE_TOOL_INPUT_KEY: "route-orders",
                "query": "recent",
            },
        )
    finally:
        current_execution.reset(token)

    assert result["success"] is True
    assert len(executor.calls) == 1
    call = executor.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://api.example.com/customers/cus-1?tenant=tenant-7"
    assert call["headers"]["Authorization"] == "Bearer runtime-secret"
    assert '"query":"recent"' in str(call["body"]).replace(" ", "")
    assert '"customer":"cus-1"' in str(call["body"]).replace(" ", "")


@pytest.mark.asyncio
async def test_provider_invented_removed_argument_is_rejected_before_http(
    monkeypatch,
) -> None:
    project_id = uuid4()
    tool_id = uuid4()
    live = _tool(config=_runtime_only_config(), tool_id=tool_id, project_id=project_id)
    executor = _HttpExecutor()
    runtime = HttpToolRuntime(executor)

    class _Registry:
        async def execute(self, runtime_tool, input_data):
            return await runtime.execute(runtime_tool, input_data)

    monkeypatch.setattr(
        gateway_module,
        "build_tool_runtime_registry",
        lambda **_kwargs: _Registry(),
    )
    monkeypatch.setattr(
        gateway_module,
        "record_tool_provider_latency",
        lambda _duration_ms: None,
    )

    context = new_execution_context()
    context.execution_context = "playground"
    context.session_id = uuid4()
    context.prepared_tools = {str(tool_id): live}
    context.tool_snapshots = {str(tool_id): tool_to_release_snapshot(live)}
    context.external_context_snapshot = {"age": 18}
    context.prepared_project_environment = {
        "MOCKED_NUMBER": PreparedProjectEnvironmentValue(
            kind="value",
            stored_value="7",
        )
    }

    token = current_execution.set(context)
    try:
        gateway = AgentToolRuntimeGateway(
            None,
            SimpleNamespace(encryption_key="test-key"),
            executor=executor,
        )
        result = await gateway.execute_tool(
            tool_id,
            {
                MCP_REMOTE_TOOL_INPUT_KEY: "route-sum",
                "b": "7",
            },
        )
    finally:
        current_execution.reset(token)

    assert result["success"] is False
    assert result["output"]["error_code"] == "HTTP_TOOL_PARAMETER_UNEXPECTED"
    assert "b" in result["error"]
    assert executor.calls == []
