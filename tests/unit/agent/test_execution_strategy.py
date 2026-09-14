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
from modules.agent.infra.execution.strategies.standard import StandardExecutionStrategy
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


def test_builtin_resolver_resolves_standard_strategy() -> None:
    resolver = BuiltinExecutionStrategyResolver()

    strategy = resolver.resolve("standard")

    assert isinstance(strategy, StandardExecutionStrategy)
    assert isinstance(strategy, ExecutionStrategy)


def test_builtin_resolver_rejects_unknown_name_defensively() -> None:
    resolver = BuiltinExecutionStrategyResolver()

    with pytest.raises(ValueError, match="Unsupported execution strategy: missing"):
        resolver.resolve("missing")


def test_resolver_builder_exposes_execution_strategy_contract() -> None:
    resolver = build_execution_strategy_resolver()

    assert isinstance(resolver.resolve("standard"), ExecutionStrategy)


@pytest.mark.asyncio
async def test_standard_strategy_composes_execution_capabilities(monkeypatch) -> None:
    calls: list[str] = []
    sentinel = InstrumentedExecution(result=SimpleNamespace(content="ok"))
    prepared = SimpleNamespace(
        model="model",
        final_model="final-model",
        final_model_factory=None,
        execute_single_tool=lambda *_args: None,
        messages=["prepared"],
        tool_name_to_id={"tool": "tool-id"},
        provider="provider",
        model_name="model-name",
        initial_phase="response_generation",
        final_json_instruction=None,
        pricing_snapshot={"input": 1},
    )

    def fake_prepare(request):
        calls.append("prepare")
        assert request.messages == ["hello"]
        return prepared

    async def fake_loop(**kwargs):
        calls.append("loop")
        assert kwargs["model"] == "model"
        assert kwargs["messages"] == ["prepared"]
        assert kwargs["tool_name_to_id"] == {"tool": "tool-id"}
        return sentinel, 7

    async def fake_finalize(**kwargs):
        calls.append("finalize")
        assert kwargs["prepared"] is prepared
        assert kwargs["execution"] is sentinel
        assert kwargs["call_index"] == 7
        return sentinel

    monkeypatch.setattr(
        "modules.agent.infra.execution.strategies.standard.prepare_execution",
        fake_prepare,
    )
    monkeypatch.setattr(
        "modules.agent.infra.execution.strategies.standard.run_tool_loop",
        fake_loop,
    )
    monkeypatch.setattr(
        "modules.agent.infra.execution.strategies.standard.finalize_execution_result",
        fake_finalize,
    )
    request = ExecutionStrategyRequest(
        llm_factory="factory",
        execute_single_tool=lambda *_args: None,  # type: ignore[arg-type]
        clean_json_answer=lambda value: value,
        agent=SimpleNamespace(),  # type: ignore[arg-type]
        api_key="secret",
        base_url="https://provider.example/v1",
        response_format={"type": "text"},
        json_enabled=False,
        has_tools=False,
        agent_tools=[],
        tool_name_to_id={},
        messages=["hello"],
        context_assembler=None,
    )

    result = await StandardExecutionStrategy().execute(request)

    assert result is sentinel
    assert calls == ["prepare", "loop", "finalize"]


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
