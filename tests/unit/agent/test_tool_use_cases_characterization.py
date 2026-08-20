from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.tools_dtos import (
    CreateSecretInput,
    CreateToolInput,
    DeleteToolInput,
    ExecuteToolInput,
    ListSecretsInput,
    ListToolsByAgentInput,
    ListToolsInput,
    TestToolInput,
    UpdateToolInput,
    UpdateToolStatusInput,
)
from modules.agent.application.use_cases import (
    CreateSecretUseCase,
    CreateToolUseCase,
    DeleteToolUseCase,
    ExecuteToolUseCase,
    ListSecretsUseCase,
    ListToolsByAgentUseCase,
    ListToolsUseCase,
    TestToolUseCase,
    UpdateToolStatusUseCase,
    UpdateToolUseCase,
)
from modules.agent.application.use_cases.tools_use_cases import GetToolUsageImpactUseCase
from modules.agent.domain.entities import Agent, AgentRelease, Secret, Tool
from modules.agent.domain.enums import (
    ReleaseStatus,
    RiskLevel,
    SecretType,
    ToolStatus,
    ToolType,
)
from modules.agent.domain.errors import ToolInUseError, ToolNotFoundError


def _tool(*, project_id, agent_id=None, status=ToolStatus.ACTIVE, name="lookup"):
    return Tool(
        id=uuid4(),
        project_id=project_id,
        agent_id=agent_id,
        name=name,
        description="Lookup customer data",
        type=ToolType.HTTP,
        config={
            "url": "https://api.example.test/customers/{{customer_id}}",
            "method": "POST",
            "headers": [
                {"key": "X-Static", "value": "static"},
                {"key": "", "value": "ignored"},
            ],
            "body": '{"customer":"{{customer_id}}","region":"{{region}}"}',
            "variables": {"region": "br"},
        },
        input_schema={"type": "object", "properties": {}},
        risk_level=RiskLevel.LOW,
        timeout_ms=4321,
        status=status,
    )


def _passthrough(mock):
    async def _call(value):
        return value

    mock.side_effect = _call


def _tool_repo(*, tool=None, project_tools=None, agent_tools=None):
    repo = SimpleNamespace(
        create=AsyncMock(),
        update=AsyncMock(),
        get_by_id=AsyncMock(return_value=tool),
        list_by_project=AsyncMock(return_value=list(project_tools or [])),
        list_by_agent=AsyncMock(return_value=list(agent_tools or [])),
        delete=AsyncMock(),
    )
    _passthrough(repo.create)
    _passthrough(repo.update)
    return repo


@pytest.mark.asyncio
async def test_create_http_tool_persists_normalized_contract_and_emits_event():
    project_id = uuid4()
    repo = _tool_repo()
    outbox = SimpleNamespace(write=AsyncMock())
    use_case = CreateToolUseCase(repo, outbox)

    result = await use_case.execute(
        CreateToolInput(
            project_id=project_id,
            name="Get Customer",
            type=ToolType.HTTP,
            config={
                "url": "https://api.example.test/customers/{{customer_id}}",
                "method": "GET",
            },
            input_schema={
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
            },
            timeout_ms=5000,
        )
    )

    repo.create.assert_awaited_once()
    persisted = repo.create.await_args.args[0]
    assert persisted.project_id == project_id
    assert persisted.name == "Get Customer"
    assert persisted.config["method"] == "GET"
    assert persisted.timeout_ms == 5000
    assert result.id == persisted.id
    outbox.write.assert_awaited_once()
    event = outbox.write.await_args.args[0]
    assert event.event_type == "agent.tool.created.v1"
    assert event.payload["tool_id"] == str(persisted.id)
    assert event.payload["project_id"] == str(project_id)


@pytest.mark.asyncio
async def test_create_tool_runs_optional_mcp_bootstrap_and_persists_bootstrapped_state():
    project_id = uuid4()
    repo = _tool_repo()
    outbox = SimpleNamespace(write=AsyncMock())

    async def bootstrap(tool):
        tool.config = {**(tool.config or {}), "mcp_status": "ready"}
        return tool

    bootstrapper = SimpleNamespace(bootstrap=AsyncMock(side_effect=bootstrap))
    use_case = CreateToolUseCase(repo, outbox, bootstrapper)

    result = await use_case.execute(
        CreateToolInput(
            project_id=project_id,
            name="MCP Search",
            type=ToolType.MCP,
            config={
                "protocol": "mcp",
                "mode": "tool",
                "exposure": "single",
                "server": {
                    "transport": "streamable_http",
                    "url": "https://mcp.example.test/mcp",
                },
                "tool_name": "search",
            },
        )
    )

    bootstrapper.bootstrap.assert_awaited_once()
    repo.update.assert_awaited_once()
    assert result.config["mcp_status"] == "ready"
    event = outbox.write.await_args.args[0]
    assert event.payload["mcp_status"] == "ready"


@pytest.mark.asyncio
async def test_create_secret_encrypts_before_persistence_and_never_returns_plaintext():
    project_id = uuid4()
    repo = SimpleNamespace(create=AsyncMock())
    outbox = SimpleNamespace(write=AsyncMock())
    cipher = SimpleNamespace(encrypt=AsyncMock(return_value="ciphertext"))

    async def create(secret):
        assert secret.encrypted_value == "ciphertext"
        assert secret.encrypted_value != "plain-secret"
        return secret

    repo.create.side_effect = create
    result = await CreateSecretUseCase(repo, outbox, cipher).execute(
        CreateSecretInput(
            project_id=project_id,
            name="API Token",
            type=SecretType.API_KEY,
            value="plain-secret",
            data={"scope": "read"},
        )
    )

    cipher.encrypt.assert_awaited_once_with("plain-secret")
    assert not hasattr(result, "value")
    assert result.name == "API Token"
    assert result.data == {"scope": "read"}
    event = outbox.write.await_args.args[0]
    assert event.event_type == "agent.secret.created.v1"
    assert "plain-secret" not in str(event.payload)


@pytest.mark.asyncio
async def test_update_tool_changes_only_requested_fields_and_can_detach_agent():
    project_id = uuid4()
    tool = _tool(project_id=project_id, agent_id=uuid4(), name="old")
    repo = _tool_repo(tool=tool)
    outbox = SimpleNamespace(write=AsyncMock())

    result = await UpdateToolUseCase(repo, outbox).execute(
        tool.id,
        UpdateToolInput(
            name="new",
            agent_id=None,
            risk_level=RiskLevel.HIGH,
            timeout_ms=9876,
        ),
    )

    assert result.name == "new"
    assert result.agent_id is None
    assert result.risk_level == RiskLevel.HIGH
    assert result.timeout_ms == 9876
    assert result.description == "Lookup customer data"
    repo.update.assert_awaited_once_with(tool)
    event = outbox.write.await_args.args[0]
    assert event.event_type == "agent.tool.updated.v1"
    assert event.payload["name"] == "new"


@pytest.mark.asyncio
async def test_update_tool_status_persists_status_and_emits_status_event():
    project_id = uuid4()
    tool = _tool(project_id=project_id)
    repo = _tool_repo(tool=tool)
    outbox = SimpleNamespace(write=AsyncMock())

    result = await UpdateToolStatusUseCase(repo, outbox).execute(
        tool.id,
        UpdateToolStatusInput(status=ToolStatus.DEPRECATED),
    )

    assert result.status == ToolStatus.DEPRECATED
    event = outbox.write.await_args.args[0]
    assert event.event_type == "agent.tool.status_changed.v1"
    assert event.payload["status"] == ToolStatus.DEPRECATED.value


def _release(*, agent_id, status, tool_id, by_snapshot=False):
    tools_config = (
        {"snapshots": [{"id": str(tool_id)}]}
        if by_snapshot
        else {"tool_ids": [str(tool_id)]}
    )
    return AgentRelease(
        id=uuid4(),
        project_id=uuid4(),
        agent_id=agent_id,
        version=str(uuid4()),
        status=status,
        runtime_config={"tools": tools_config},
    )


@pytest.mark.asyncio
async def test_tool_usage_impact_counts_draft_staging_production_and_history():
    project_id = uuid4()
    tool = _tool(project_id=project_id)
    agent_a = Agent(id=uuid4(), project_id=project_id, name="A", model="m")
    agent_b = Agent(id=uuid4(), project_id=project_id, name="B", model="m")
    tool_repo = _tool_repo(tool=tool)
    agent_repo = SimpleNamespace(list_by_project=AsyncMock(return_value=[agent_a, agent_b]))
    release_repo = SimpleNamespace(list_by_agent=AsyncMock())

    releases = {
        agent_a.id: [
            _release(agent_id=agent_a.id, status=ReleaseStatus.draft, tool_id=tool.id),
            _release(agent_id=agent_a.id, status=ReleaseStatus.staging, tool_id=tool.id),
            _release(agent_id=agent_a.id, status=ReleaseStatus.production, tool_id=tool.id),
            _release(agent_id=agent_a.id, status=ReleaseStatus.released, tool_id=tool.id),
        ],
        agent_b.id: [
            _release(
                agent_id=agent_b.id,
                status=ReleaseStatus.production,
                tool_id=tool.id,
                by_snapshot=True,
            )
        ],
    }

    async def list_by_agent(agent_id):
        return releases[agent_id]

    release_repo.list_by_agent.side_effect = list_by_agent
    impact = await GetToolUsageImpactUseCase(
        tool_repo,
        agent_repo,
        release_repo,
    ).execute(tool.id)

    assert impact.in_use is True
    assert impact.can_delete is False
    assert impact.draft_agents == 1
    assert impact.staging_agents == 1
    assert impact.production_agents == 2
    assert impact.historical_releases == 1
    assert impact.total_references == 5


@pytest.mark.asyncio
async def test_deprecated_unreferenced_tool_can_be_deleted_but_cannot_be_retired_again():
    project_id = uuid4()
    tool = _tool(project_id=project_id, status=ToolStatus.DEPRECATED)
    tool_repo = _tool_repo(tool=tool)
    agent_repo = SimpleNamespace(list_by_project=AsyncMock(return_value=[]))
    release_repo = SimpleNamespace(list_by_agent=AsyncMock(return_value=[]))

    impact = await GetToolUsageImpactUseCase(
        tool_repo,
        agent_repo,
        release_repo,
    ).execute(tool.id)

    assert impact.in_use is False
    assert impact.can_delete is True
    assert impact.can_retire is False

    await DeleteToolUseCase(tool_repo, agent_repo, release_repo).execute(
        DeleteToolInput(tool_id=tool.id)
    )
    tool_repo.delete.assert_awaited_once_with(tool.id)


@pytest.mark.asyncio
async def test_delete_tool_is_blocked_when_any_release_references_it():
    project_id = uuid4()
    tool = _tool(project_id=project_id)
    agent = Agent(id=uuid4(), project_id=project_id, name="A", model="m")
    tool_repo = _tool_repo(tool=tool)
    agent_repo = SimpleNamespace(list_by_project=AsyncMock(return_value=[agent]))
    release_repo = SimpleNamespace(
        list_by_agent=AsyncMock(
            return_value=[
                _release(
                    agent_id=agent.id,
                    status=ReleaseStatus.production,
                    tool_id=tool.id,
                )
            ]
        )
    )

    with pytest.raises(ToolInUseError) as exc_info:
        await DeleteToolUseCase(tool_repo, agent_repo, release_repo).execute(
            DeleteToolInput(tool_id=tool.id)
        )

    assert exc_info.value.impact.total_references == 1
    tool_repo.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_tool_resolves_secrets_variables_body_url_and_timeout():
    project_id = uuid4()
    tool = _tool(project_id=project_id)
    repo = _tool_repo(tool=tool)
    resolver = SimpleNamespace(
        resolve_headers=AsyncMock(return_value={"Authorization": "Bearer secret"})
    )
    executor = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                success=True,
                output={"status": "ok"},
                duration_ms=12.5,
                error=None,
            )
        )
    )

    result = await ExecuteToolUseCase(repo, executor, resolver).execute(
        ExecuteToolInput(
            tool_id=tool.id,
            input_data={"customer_id": "42", "region": "sc"},
        )
    )

    resolver.resolve_headers.assert_awaited_once_with(tool.config["headers"], project_id)
    executor.execute.assert_awaited_once_with(
        method="POST",
        url="https://api.example.test/customers/42",
        headers={"Authorization": "Bearer secret"},
        body='{"customer":"42","region":"sc"}',
        timeout_ms=4321,
    )
    assert result.success is True
    assert result.output == {"status": "ok"}


@pytest.mark.asyncio
async def test_execute_tool_without_secret_resolver_uses_literal_nonempty_headers():
    project_id = uuid4()
    tool = _tool(project_id=project_id)
    repo = _tool_repo(tool=tool)
    executor = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                success=True,
                output={},
                duration_ms=1,
                error=None,
            )
        )
    )

    await ExecuteToolUseCase(repo, executor).execute(
        ExecuteToolInput(tool_id=tool.id, input_data={"customer_id": "1"})
    )

    assert executor.execute.await_args.kwargs["headers"] == {"X-Static": "static"}


@pytest.mark.asyncio
async def test_execute_tool_rejects_inactive_tool_before_external_execution():
    project_id = uuid4()
    tool = _tool(project_id=project_id, status=ToolStatus.INACTIVE)
    repo = _tool_repo(tool=tool)
    executor = SimpleNamespace(execute=AsyncMock())

    with pytest.raises(ToolNotFoundError):
        await ExecuteToolUseCase(repo, executor).execute(
            ExecuteToolInput(tool_id=tool.id, input_data={})
        )

    executor.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_test_tool_interpolates_variables_and_returns_transport_result():
    executor = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                success=True,
                status_code=200,
                headers={"content-type": "application/json"},
                body='{"ok":true}',
                duration_ms=4,
                error=None,
            )
        )
    )

    result = await TestToolUseCase(executor).execute(
        TestToolInput(
            type=ToolType.HTTP,
            config={
                "url": "https://example.test/{{tenant}}/items/{{id}}",
                "method": "POST",
                "headers": [{"key": "X-Test", "value": "yes"}],
                "body": "tenant={{tenant}};id={{id}}",
                "variables": {"tenant": "default"},
            },
            input_data={"tenant": "override", "id": 7},
        )
    )

    executor.execute.assert_awaited_once_with(
        method="POST",
        url="https://example.test/override/items/7",
        headers={"X-Test": "yes"},
        body="tenant=override;id=7",
        timeout_ms=30000,
    )
    assert result.success is True
    assert result.status_code == 200
    assert result.body == '{"ok":true}'


@pytest.mark.asyncio
async def test_list_tool_and_secret_use_cases_preserve_scope_semantics():
    project_id = uuid4()
    agent_id = uuid4()
    tool = _tool(project_id=project_id, agent_id=agent_id)
    secret = Secret(
        id=uuid4(),
        project_id=project_id,
        name="token",
        encrypted_value="ciphertext",
    )
    tool_repo = _tool_repo(project_tools=[tool], agent_tools=[tool])
    secret_repo = SimpleNamespace(list_by_project=AsyncMock(return_value=[secret]))

    assert await ListToolsUseCase(tool_repo).execute(ListToolsInput(project_id=None)) == []
    tool_repo.list_by_project.assert_not_awaited()

    project_tools = await ListToolsUseCase(tool_repo).execute(
        ListToolsInput(project_id=project_id)
    )
    agent_tools = await ListToolsByAgentUseCase(tool_repo).execute(
        ListToolsByAgentInput(agent_id=agent_id)
    )
    assert await ListSecretsUseCase(secret_repo).execute(
        ListSecretsInput(project_id=None)
    ) == []
    project_secrets = await ListSecretsUseCase(secret_repo).execute(
        ListSecretsInput(project_id=project_id)
    )

    assert project_tools == [tool]
    assert agent_tools == [tool]
    assert project_secrets == [secret]
    tool_repo.list_by_project.assert_awaited_once_with(project_id)
    tool_repo.list_by_agent.assert_awaited_once_with(agent_id)
    secret_repo.list_by_project.assert_awaited_once_with(project_id)
