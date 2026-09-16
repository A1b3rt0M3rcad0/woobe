from __future__ import annotations

from types import SimpleNamespace

import pytest

from modules.agent.application.execution_strategy_config import (
    DEFAULT_EXECUTION_STRATEGY,
    canonicalize_execution_strategy_runtime_config,
    execution_strategy_from_runtime_config,
)
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_strategy import (
    ExecutableExecutionStrategy,
    ExecutionStrategy,
    ExecutionStrategyRequest,
)
from modules.agent.application.use_cases.ai_agent_cases import (
    _force_strict_json_settings,
)
from modules.agent.application.use_cases.release_lifecycle_use_cases_v2 import (
    _canonical_runtime_config,
)
from modules.agent.infra.execution.instrumented_primary_mixin import (
    InstrumentedPrimaryExecutionMixin,
)
from modules.agent.infra.execution.release_runtime_resolver import ReleaseRuntimeResolver
from modules.agent.infra.execution.strategies.resolver import (
    BuiltinExecutionStrategyResolver,
    build_execution_strategy_resolver,
)
from modules.agent.infra.execution.strategies.standard import (
    StandardExecutionStrategy,
    build_standard_strategy_definition,
)
from modules.agent.infra.execution.strategy_runtime.runner import StrategyExecutionRunner
from shared.contracts.errors import ValidationError


def test_missing_execution_strategy_is_permanently_standard() -> None:
    assert execution_strategy_from_runtime_config(None) == DEFAULT_EXECUTION_STRATEGY
    assert execution_strategy_from_runtime_config({}) == "standard"
    assert execution_strategy_from_runtime_config({"other": True}) == "standard"


def test_explicit_standard_strategy_is_normalized() -> None:
    assert execution_strategy_from_runtime_config(
        {"execution_strategy": "  STANDARD  "}
    ) == "standard"


@pytest.mark.parametrize("value", ["", " ", 1, True, {}, []])
def test_invalid_execution_strategy_shape_is_rejected(value: object) -> None:
    with pytest.raises(ValidationError, match="execution_strategy"):
        execution_strategy_from_runtime_config({"execution_strategy": value})


def test_unknown_execution_strategy_is_rejected_before_runtime() -> None:
    with pytest.raises(ValidationError, match="Unsupported execution strategy: react"):
        execution_strategy_from_runtime_config({"execution_strategy": "react"})


def test_canonicalization_freezes_standard_without_losing_other_runtime_config() -> None:
    source = {"other": {"enabled": True}}

    result = canonicalize_execution_strategy_runtime_config(source)

    assert result == {
        "other": {"enabled": True},
        "execution_strategy": "standard",
    }
    assert "execution_strategy" not in source


def test_new_agent_settings_freeze_standard_strategy_explicitly() -> None:
    agent = SimpleNamespace(settings={})

    _force_strict_json_settings(agent, initialize_context_manager=True)

    assert agent.settings["runtime_config"]["execution_strategy"] == "standard"


def test_release_runtime_config_preserves_explicit_execution_strategy() -> None:
    runtime_config = _canonical_runtime_config({"execution_strategy": "STANDARD"})

    assert runtime_config["execution_strategy"] == "standard"
    assert "context_assembler" in runtime_config
    assert "context" in runtime_config
    assert "rag" in runtime_config


def test_legacy_release_snapshot_keeps_absence_with_standard_semantics() -> None:
    runtime_config = _canonical_runtime_config({})

    assert "execution_strategy" not in runtime_config
    assert execution_strategy_from_runtime_config(runtime_config) == "standard"


def test_release_runtime_config_rejects_unknown_execution_strategy() -> None:
    with pytest.raises(ValidationError, match="Unsupported execution strategy: react"):
        _canonical_runtime_config({"execution_strategy": "react"})


def test_standard_definition_exposes_sdk_strategy() -> None:
    definition = build_standard_strategy_definition()
    strategy = definition.strategy_factory()

    assert definition.name == "standard"
    assert isinstance(strategy, StandardExecutionStrategy)
    assert isinstance(strategy, ExecutionStrategy)


def test_builtin_resolver_resolves_runtime_ready_standard_adapter() -> None:
    resolver = BuiltinExecutionStrategyResolver()

    strategy = resolver.resolve("standard")

    assert isinstance(strategy, StrategyExecutionRunner)
    assert isinstance(strategy, ExecutableExecutionStrategy)
    assert strategy.definition.name == "standard"


def test_builtin_resolver_rejects_unknown_name_defensively() -> None:
    resolver = BuiltinExecutionStrategyResolver()

    with pytest.raises(ValueError, match="Unsupported execution strategy: missing"):
        resolver.resolve("missing")


def test_resolver_builder_exposes_outer_execution_contract() -> None:
    resolver = build_execution_strategy_resolver()

    assert isinstance(resolver.resolve("standard"), ExecutableExecutionStrategy)


class _RecordingStrategy:
    def __init__(self) -> None:
        self.request: ExecutionStrategyRequest | None = None

    async def execute(self, request: ExecutionStrategyRequest) -> InstrumentedExecution:
        self.request = request
        return InstrumentedExecution(result=SimpleNamespace(content="ok", usage_metadata=None))


class _RecordingResolver:
    def __init__(self, strategy: _RecordingStrategy) -> None:
        self.strategy = strategy
        self.names: list[str] = []

    def resolve(self, name: str) -> _RecordingStrategy:
        self.names.append(name)
        return self.strategy


class _RuntimeHost(InstrumentedPrimaryExecutionMixin):
    _llm_factory = "llm-factory"
    _context_assembler = None

    async def _execute_single_tool(self, tool_call: dict, tool_id: str) -> dict:
        return {"tool_call": tool_call, "tool_id": tool_id}

    def _clean_json_answer(self, answer: str) -> str:
        return answer


@pytest.mark.asyncio
async def test_agent_runtime_requires_strategy_resolver_from_composition() -> None:
    runtime = _RuntimeHost()
    agent = SimpleNamespace(settings={})

    with pytest.raises(
        RuntimeError,
        match="Agent execution strategy resolver is not configured",
    ):
        await runtime._execute_llm(
            agent=agent,
            api_key="secret",
            base_url=None,
            response_format={},
            json_enabled=False,
            has_tools=False,
            agent_tools=[],
            tool_name_to_id={},
            messages=["hello"],
        )


@pytest.mark.asyncio
async def test_agent_runtime_resolves_strategy_from_agent_runtime_config() -> None:
    strategy = _RecordingStrategy()
    resolver = _RecordingResolver(strategy)
    runtime = _RuntimeHost()
    runtime.configure_execution_strategy_resolver(resolver)
    agent = SimpleNamespace(
        settings={"runtime_config": {"execution_strategy": "standard"}},
    )

    result, tool_calls, tool_was_called, repair_latency = await runtime._execute_llm(
        agent=agent,
        api_key="secret",
        base_url=None,
        response_format={},
        json_enabled=False,
        has_tools=False,
        agent_tools=[],
        tool_name_to_id={},
        messages=["hello"],
    )

    assert result.content == "ok"
    assert tool_calls == []
    assert tool_was_called is False
    assert repair_latency is None
    assert resolver.names == ["standard"]
    assert strategy.request is not None
    assert strategy.request.agent is agent
    assert strategy.request.messages == ["hello"]


@pytest.mark.asyncio
async def test_agent_runtime_keeps_legacy_agent_on_standard_strategy() -> None:
    strategy = _RecordingStrategy()
    resolver = _RecordingResolver(strategy)
    runtime = _RuntimeHost()
    runtime.configure_execution_strategy_resolver(resolver)
    agent = SimpleNamespace(settings={})

    await runtime._execute_llm(
        agent=agent,
        api_key="secret",
        base_url=None,
        response_format={},
        json_enabled=False,
        has_tools=False,
        agent_tools=[],
        tool_name_to_id={},
        messages=["legacy"],
    )

    assert resolver.names == ["standard"]


@pytest.mark.asyncio
async def test_frozen_release_runtime_config_wins_over_mutable_agent_state() -> None:
    strategy = _RecordingStrategy()
    resolver = _RecordingResolver(strategy)
    runtime = _RuntimeHost()
    runtime.configure_execution_strategy_resolver(resolver)
    agent = SimpleNamespace(
        settings={"runtime_config": {"execution_strategy": "react"}},
    )

    ReleaseRuntimeResolver._apply_runtime_config_snapshot(
        agent,
        {"execution_strategy": "standard"},
    )

    await runtime._execute_llm(
        agent=agent,
        api_key="secret",
        base_url=None,
        response_format={},
        json_enabled=False,
        has_tools=False,
        agent_tools=[],
        tool_name_to_id={},
        messages=["release"],
    )

    assert resolver.names == ["standard"]
    assert agent.settings["runtime_config"] == {"execution_strategy": "standard"}
