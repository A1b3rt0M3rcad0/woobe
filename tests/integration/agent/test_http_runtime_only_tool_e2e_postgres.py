from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from modules.agent.application.context_managers.standard import StandardContextAssembler
from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.execution_snapshot import (
    AgentExecutionSnapshotResolver,
    apply_agent_execution_snapshot,
)
from modules.agent.application.interfaces.ports import ExecutionResult
from modules.agent.application.tool_release_snapshots import tool_to_release_snapshot
from modules.agent.domain.entities import Tool
from modules.agent.domain.enums import RiskLevel, ToolStatus, ToolType
from modules.agent.infra.database.models import (
    AgentModel,
    AgentToolModel,
    ProviderCredentialModel,
    SessionModel,
)
from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.execution.agent_tool_runtime_gateway import AgentToolRuntimeGateway
from modules.agent.infra.execution.canonical_execution_snapshot_runtime_resolver import (
    configure_execution_snapshot_runtime,
)
from modules.agent.infra.execution.frozen_snapshot_runtime import (
    FrozenSnapshotStructuredOutputRuntime,
)
from modules.agent.infra.execution.strategies.resolver import (
    build_execution_strategy_resolver,
)
from modules.core.infra.database.models import (
    ProjectEnvironmentKeyModel,
    ProjectEnvironmentValueModel,
    ProjectModel,
)
from shared.infra.config import Settings
from shared.infra.crypto import encrypt_secret
from shared.infra.database.session import create_engine, create_session_factory


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
                "description": "Old model-provided operand.",
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


def _live_config() -> dict:
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
                "description": "Runtime-only operands.",
                "method": "GET",
                "path": (
                    "/v4/?expr={{external_context.age}}"
                    "%2B{{project_env.MOCKED_NUMBER}}"
                ),
                "headers": [],
                # Historical schema noise intentionally remains in storage. Both
                # model exposure and execution must compile from the current template.
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


class _RecordingToolModel:
    def __init__(self) -> None:
        self.bound_tools: list[dict] = []
        self.invocations = 0

    def bind_tools(self, tools, *, tool_choice):
        assert tool_choice == "auto"
        self.bound_tools = deepcopy(list(tools))
        return self

    async def ainvoke(self, messages):
        self.invocations += 1
        has_tool_result = any(isinstance(message, ToolMessage) for message in messages)
        if has_tool_result:
            response = AIMessage(content="runtime-only tool completed")
        else:
            tool_name = self.bound_tools[0]["function"]["name"]
            response = AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-runtime-only",
                        "name": tool_name,
                        "args": {},
                    }
                ],
            )
        response.usage_metadata = {
            "input_tokens": 5,
            "output_tokens": 3,
            "total_tokens": 8,
        }
        response.response_metadata = {
            "provider": "openai",
            "model": "provider-mock",
        }
        return response


class _RecordingProviderFactory:
    def __init__(self) -> None:
        self.model = _RecordingToolModel()

    def create_chat_model(self, **_kwargs):
        return self.model


class _RecordingHttpExecutor:
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


@pytest.mark.asyncio
async def test_existing_draft_session_uses_edited_live_tool_and_runtime_only_values() -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    project_id = uuid4()
    credential_id = uuid4()
    agent_id = uuid4()
    tool_id = uuid4()
    session_id = uuid4()
    env_key_id = uuid4()

    stale_tool = Tool(
        id=tool_id,
        project_id=project_id,
        name="api.mathjs.org",
        description="Math API",
        type=ToolType.HTTP,
        config=_stale_config(),
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        risk_level=RiskLevel.LOW,
        status=ToolStatus.ACTIVE,
    )
    stale_snapshot = tool_to_release_snapshot(stale_tool)

    async with session_factory() as session, session.begin():
        session.add(
            ProjectModel(
                id=project_id,
                workspace_id=uuid4(),
                name="Runtime-only Tool E2E",
                slug=f"runtime-only-tool-{project_id}",
                status="active",
                data={},
            )
        )
        await session.flush()

        session.add(
            ProviderCredentialModel(
                id=credential_id,
                project_id=project_id,
                provider="openai",
                name=f"runtime-only-{credential_id}",
                encrypted_secret=encrypt_secret(
                    "provider-mock-key",
                    settings.encryption_key,
                ),
                status="active",
                meta={},
            )
        )
        await session.flush()

        session.add(
            AgentModel(
                id=agent_id,
                project_id=project_id,
                provider_credential_id=credential_id,
                fallback_credential_id=None,
                name="Runtime-only Tool Agent",
                description="",
                type="assistant",
                system_prompt="Use the bound Tool once, then report completion.",
                provider="openai",
                model="provider-mock",
                fallback_provider=None,
                fallback_model=None,
                temperature=0.0,
                max_output_tokens=128,
                session_mode="stateful",
                status="active",
                settings={
                    "external_context_contract": {
                        "age": {
                            "schema": {"type": "integer"},
                            "required": True,
                            "model": {"expose": False},
                        }
                    },
                    "runtime_config": {
                        "tools": {
                            "tool_ids": [str(tool_id)],
                            "snapshots": [stale_snapshot],
                        }
                    },
                },
            )
        )
        await session.flush()

        # This is the edited live Tool. The Agent snapshot above intentionally still
        # contains the historical {{b}} route.
        session.add(
            AgentToolModel(
                id=tool_id,
                project_id=project_id,
                agent_id=None,
                name="api.mathjs.org",
                description="Math API",
                type="http",
                config=_live_config(),
                input_schema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
                output_schema=None,
                risk_level="low",
                timeout_ms=30000,
                status="active",
            )
        )
        await session.flush()

        session.add(
            SessionModel(
                id=session_id,
                project_id=project_id,
                agent_id=agent_id,
                runtime_environment="draft",
                opened_release_id=None,
                external_session_id=None,
                tenant_id=None,
                user_id=None,
                status="active",
                mode="chat",
                data=None,
            )
        )

        session.add(
            ProjectEnvironmentKeyModel(
                id=env_key_id,
                project_id=project_id,
                key="MOCKED_NUMBER",
                kind="value",
            )
        )
        await session.flush()
        session.add(
            ProjectEnvironmentValueModel(
                id=uuid4(),
                key_id=env_key_id,
                environment="draft",
                stored_value="7",
            )
        )

    configure_execution_snapshot_runtime(
        AgentExecutionSnapshotResolver,
        apply_agent_execution_snapshot,
    )
    transactions = AgentRuntimeTransactionRunner(lambda: AgentUnitOfWork(engine))
    provider_factory = _RecordingProviderFactory()
    http_executor = _RecordingHttpExecutor()
    tool_runtime = AgentToolRuntimeGateway(
        transactions,
        settings,
        http_executor,
    )
    runtime = FrozenSnapshotStructuredOutputRuntime(
        transactions=transactions,
        llm_factory=provider_factory,
        encryption_key=settings.encryption_key,
        tool_executor_factory=tool_runtime.execute_tool,
    )
    runtime.configure_context_assembler(StandardContextAssembler())
    runtime.configure_execution_strategy_resolver(build_execution_strategy_resolver())
    runtime.configure_runtime_tool_reader(tool_runtime.read_runtime_tools)

    try:
        result = await runtime.execute(
            AskInput(
                project_id=project_id,
                agent_id=agent_id,
                session_id=session_id,
                message="call the math tool",
                execution_context="playground",
                external_context={"age": 18},
                metadata={"source": "playground"},
            )
        )
    finally:
        await engine.dispose()

    assert result.answer == "runtime-only tool completed"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].input == {}

    assert provider_factory.model.bound_tools
    parameters = provider_factory.model.bound_tools[0]["function"]["parameters"]
    assert parameters == {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }
    assert "b" not in str(provider_factory.model.bound_tools)

    assert http_executor.calls == [
        {
            "method": "GET",
            "url": "https://api.mathjs.org/v4/?expr=18%2B7",
            "headers": {},
            "body": None,
            "timeout_ms": 30000,
        }
    ]
