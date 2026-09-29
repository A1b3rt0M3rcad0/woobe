from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.knowledge_strategy_registry import (
    build_knowledge_strategy_registry,
)
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyRequest
from modules.agent.application.use_cases.auto_compatible_release_lifecycle import (
    AutoCompatibleReleaseLifecycleUseCase,
)
from modules.agent.application.use_cases.release_lifecycle_use_cases import (
    _canonical_runtime_config,
)
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.infra.execution.instrumented_primary_mixin import (
    InstrumentedPrimaryExecutionMixin,
)
from modules.agent.infra.execution.release_runtime_resolver import ReleaseRuntimeResolver


class _ReleaseRepository:
    def __init__(self, *items: AgentRelease) -> None:
        self.items = {item.id: item for item in items}

    async def get_by_id(self, item_id):
        return self.items.get(item_id)

    async def get_active_production(self, agent_id):
        return next(
            (
                item
                for item in self.items.values()
                if item.agent_id == agent_id and item.status == ReleaseStatus.production
            ),
            None,
        )

    async def save(self, item):
        self.items[item.id] = item
        return item

    async def list_by_status(self, agent_id, status):
        value = status.value if hasattr(status, "value") else status
        return [
            item
            for item in self.items.values()
            if item.agent_id == agent_id
            and getattr(item.status, "value", item.status) == value
        ]

    async def list_by_agent(self, agent_id):
        return [item for item in self.items.values() if item.agent_id == agent_id]


class _RecordingStrategy:
    async def execute(self, request: ExecutionStrategyRequest) -> InstrumentedExecution:
        return InstrumentedExecution(
            result=SimpleNamespace(content="ok", usage_metadata=None),
        )


class _RecordingResolver:
    def __init__(self) -> None:
        self.names: list[str] = []

    def resolve(self, name: str) -> _RecordingStrategy:
        self.names.append(name)
        return _RecordingStrategy()


class _RuntimeHost(InstrumentedPrimaryExecutionMixin):
    _llm_factory = "llm-factory"
    _context_assembler = None

    async def _execute_single_tool(self, tool_call: dict, tool_id: str) -> dict:
        return {"tool_call": tool_call, "tool_id": tool_id}

    def _clean_json_answer(self, answer: str) -> str:
        return answer


@pytest.mark.asyncio
async def test_strategy_survives_draft_staging_production_and_drives_runtime() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    runtime_config = {
        "execution_strategy": "standard",
        "other_runtime_setting": {"enabled": True},
    }
    expected_snapshot_runtime = _canonical_runtime_config(runtime_config)
    draft = AgentRelease(
        project_id=project_id,
        agent_id=agent_id,
        version="draft",
        status=ReleaseStatus.draft,
        provider="openai",
        model="model-a",
        session_mode="stateless",
        runtime_config=runtime_config,
    )
    repo = _ReleaseRepository(draft)
    lifecycle = AutoCompatibleReleaseLifecycleUseCase(repo)

    staging = await lifecycle.execute(
        agent_id,
        draft.id,
        target_status="staging",
    )
    production = await lifecycle.execute(
        agent_id,
        staging.id,
        target_status="production",
    )

    assert staging.runtime_config == expected_snapshot_runtime
    assert production.runtime_config == expected_snapshot_runtime
    assert staging.runtime_config["execution_strategy"] == "standard"
    assert staging.runtime_config["other_runtime_setting"] == {"enabled": True}

    draft.runtime_config["execution_strategy"] = "react"
    stored_production = await repo.get_by_id(production.id)
    assert stored_production is not None
    assert stored_production.runtime_config["execution_strategy"] == "standard"

    # Simulate mutable Agent state diverging after the immutable Production snapshot.
    # Runtime resolution must use the Release snapshot, not current draft state.
    agent = SimpleNamespace(
        settings={"runtime_config": {"execution_strategy": "react"}},
    )
    ReleaseRuntimeResolver._apply_runtime_config_snapshot(
        agent,
        production.runtime_config,
    )

    resolver = _RecordingResolver()
    runtime = _RuntimeHost()
    runtime.configure_execution_strategy_resolver(resolver)
    runtime.configure_knowledge_strategy_resolver(build_knowledge_strategy_registry())
    result, _, _, _ = await runtime._execute_llm(
        agent=agent,
        api_key="secret",
        base_url=None,
        response_format={},
        json_enabled=False,
        has_tools=False,
        agent_tools=[],
        tool_name_to_id={},
        messages=["release-bound execution"],
    )

    assert result.content == "ok"
    assert resolver.names == ["standard"]
    assert agent.settings["runtime_config"] == expected_snapshot_runtime
