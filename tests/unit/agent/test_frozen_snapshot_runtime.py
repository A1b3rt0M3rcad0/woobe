from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskOutput, UsageInfo
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.domain.entities import Agent
from modules.agent.domain.enums import Provider, SessionMode
from modules.agent.infra.execution import frozen_snapshot_runtime as runtime_module
from modules.agent.infra.execution.frozen_snapshot_runtime import (
    FrozenSnapshotStructuredOutputRuntime,
)
from modules.agent.infra.execution.transaction_bounded_structured_output import (
    TransactionBoundedStructuredOutputRuntime,
)


def test_frozen_snapshot_replaces_mutable_draft_runtime_state_exactly() -> None:
    current_provider_model_id = uuid4()
    current_credential_id = uuid4()
    current_fallback_model_id = uuid4()
    current_fallback_credential_id = uuid4()
    frozen_provider_model_id = uuid4()
    frozen_credential_id = uuid4()
    frozen_knowledge_version_id = uuid4()

    agent = Agent(
        project_id=uuid4(),
        provider_model_id=current_provider_model_id,
        provider_credential_id=current_credential_id,
        fallback_provider_model_id=current_fallback_model_id,
        fallback_credential_id=current_fallback_credential_id,
        provider=Provider.anthropic,
        model="current-model",
        fallback_provider=Provider.openai,
        fallback_model="current-fallback",
        system_prompt="current prompt",
        temperature=0.9,
        max_output_tokens=900,
        session_mode=SessionMode.stateless,
        settings={
            "knowledge_version_id": str(uuid4()),
            "response_format": {"enabled": False},
            "runtime_config": {
                "rag": {"top_k": 99},
                "tools": {"tool_ids": [str(uuid4())]},
            },
        },
    )
    snapshot = {
        "system_prompt": "frozen prompt",
        "provider_model_id": str(frozen_provider_model_id),
        "provider_credential_id": str(frozen_credential_id),
        "provider": "openai",
        "model": "frozen-model",
        "fallback_provider_model_id": None,
        "fallback_credential_id": None,
        "fallback_provider": None,
        "fallback_model": None,
        "temperature": None,
        "max_output_tokens": 321,
        "session_mode": "stateful",
        "knowledge_version_id": str(frozen_knowledge_version_id),
        "response_format": {
            "enabled": True,
            "type": "json",
            "schema": {"type": "object"},
        },
        "runtime_config": {
            "rag": {"top_k": 4, "candidate_k": 8},
            "tools": {"tool_ids": []},
        },
    }

    runtime = FrozenSnapshotStructuredOutputRuntime.__new__(
        FrozenSnapshotStructuredOutputRuntime
    )
    resolved = runtime._apply_snapshot_override(agent, snapshot)

    assert resolved is agent
    assert agent.system_prompt == "frozen prompt"
    assert agent.provider_model_id == frozen_provider_model_id
    assert agent.provider_credential_id == frozen_credential_id
    assert agent.provider == Provider.openai
    assert agent.model == "frozen-model"
    assert agent.fallback_provider_model_id is None
    assert agent.fallback_credential_id is None
    assert agent.fallback_provider is None
    assert agent.fallback_model is None
    assert agent.temperature is None
    assert agent.max_output_tokens == 321
    assert agent.session_mode == SessionMode.stateful
    assert agent.settings == {
        "knowledge_version_id": str(frozen_knowledge_version_id),
        "response_format": {
            "enabled": True,
            "type": "json",
            "schema": {"type": "object"},
        },
        "runtime_config": {
            "rag": {"top_k": 4, "candidate_k": 8},
            "tools": {"tool_ids": []},
        },
    }


class _MessageRepository:
    def __init__(self, messages):
        self.messages = list(messages)
        self.create_calls = 0

    async def list_by_session(self, _session_id):
        return list(self.messages)

    async def get_by_id(self, message_id):
        return next(
            (message for message in self.messages if message.id == message_id),
            None,
        )

    async def create(self, _message):
        self.create_calls += 1
        raise AssertionError("rerun must not persist the original user input twice")


@pytest.mark.asyncio
async def test_rerun_reuses_original_user_message_and_replays_prior_history_only() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()
    original_input_id = uuid4()
    session = SimpleNamespace(id=session_id, project_id=project_id, agent_id=agent_id)
    agent = SimpleNamespace(id=agent_id)
    messages = [
        SimpleNamespace(
            id=uuid4(),
            project_id=project_id,
            agent_id=agent_id,
            session_id=session_id,
            role="user",
            content="earlier question",
            data=None,
        ),
        SimpleNamespace(
            id=uuid4(),
            project_id=project_id,
            agent_id=agent_id,
            session_id=session_id,
            role="assistant",
            content="earlier answer",
            data=None,
        ),
        SimpleNamespace(
            id=original_input_id,
            project_id=project_id,
            agent_id=agent_id,
            session_id=session_id,
            role="user",
            content="original input",
            data=None,
        ),
        SimpleNamespace(
            id=uuid4(),
            project_id=project_id,
            agent_id=agent_id,
            session_id=session_id,
            role="assistant",
            content="original answer must not enter rerun context",
            data=None,
        ),
        SimpleNamespace(
            id=uuid4(),
            project_id=project_id,
            agent_id=agent_id,
            session_id=session_id,
            role="user",
            content="later question must not enter rerun context",
            data=None,
        ),
    ]
    repository = _MessageRepository(messages)
    runtime = FrozenSnapshotStructuredOutputRuntime.__new__(
        FrozenSnapshotStructuredOutputRuntime
    )

    token = runtime_module._rerun_input_message_id.set(original_input_id)
    try:
        history = await runtime._load_history(repository, session)
        reused = await runtime._save_user_message(
            None,
            repository,
            session,
            "original input",
            agent,
        )
    finally:
        runtime_module._rerun_input_message_id.reset(token)

    assert [(type(item).__name__, item.content) for item in history] == [
        ("HumanMessage", "earlier question"),
        ("AIMessage", "earlier answer"),
    ]
    assert reused.id == original_input_id
    assert repository.create_calls == 0


@pytest.mark.asyncio
async def test_rerun_rejects_input_message_from_another_session() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    session = SimpleNamespace(id=uuid4(), project_id=project_id, agent_id=agent_id)
    agent = SimpleNamespace(id=agent_id)
    input_message_id = uuid4()
    repository = _MessageRepository(
        [
            SimpleNamespace(
                id=input_message_id,
                project_id=project_id,
                agent_id=agent_id,
                session_id=uuid4(),
                role="user",
                content="original input",
                data=None,
            )
        ]
    )
    runtime = FrozenSnapshotStructuredOutputRuntime.__new__(
        FrozenSnapshotStructuredOutputRuntime
    )

    token = runtime_module._rerun_input_message_id.set(input_message_id)
    try:
        with pytest.raises(Exception, match="selected Session"):
            await runtime._load_history(repository, session)
    finally:
        runtime_module._rerun_input_message_id.reset(token)


def test_network_frozen_snapshot_replaces_live_external_context_contract() -> None:
    live_contract = {
        "legacy_name": {
            "schema": {"type": "string"},
            "required": False,
            "model": {"expose": False},
        }
    }
    frozen_contract = {
        "name": {
            "schema": {"type": "string"},
            "required": True,
            "model": {"expose": True},
            "description": "Name supplied by the Network host application.",
        },
        "age": {
            "schema": {"type": "integer"},
            "required": True,
            "model": {"expose": False},
        },
    }
    agent = Agent(
        project_id=uuid4(),
        provider=Provider.custom,
        model="current-model",
        session_mode=SessionMode.stateful,
        settings={
            "external_context_contract": live_contract,
            "runtime_config": {},
        },
    )
    snapshot = {
        "provider": "custom",
        "model": "frozen-model",
        "session_mode": "stateful",
        "external_context_contract": frozen_contract,
        "runtime_config": {},
    }

    runtime = FrozenSnapshotStructuredOutputRuntime.__new__(
        FrozenSnapshotStructuredOutputRuntime
    )
    runtime._apply_snapshot_override(agent, snapshot)

    assert agent.settings["external_context_contract"] == frozen_contract
    assert agent.settings["external_context_contract"] != live_contract


def test_network_frozen_snapshot_can_restore_external_context_contract_when_live_agent_has_none() -> None:
    frozen_contract = {
        "name": {
            "schema": {"type": "string"},
            "required": True,
            "model": {"expose": True},
        }
    }
    agent = Agent(
        project_id=uuid4(),
        provider=Provider.custom,
        model="current-model",
        session_mode=SessionMode.stateful,
        settings={"runtime_config": {}},
    )
    snapshot = {
        "provider": "custom",
        "model": "frozen-model",
        "session_mode": "stateful",
        "external_context_contract": frozen_contract,
        "runtime_config": {},
    }

    runtime = FrozenSnapshotStructuredOutputRuntime.__new__(
        FrozenSnapshotStructuredOutputRuntime
    )
    runtime._apply_snapshot_override(agent, snapshot)

    assert agent.settings["external_context_contract"] == frozen_contract


def test_frozen_snapshot_explicit_null_clears_live_external_context_contract() -> None:
    agent = Agent(
        project_id=uuid4(),
        provider=Provider.custom,
        model="current-model",
        session_mode=SessionMode.stateful,
        settings={
            "external_context_contract": {
                "legacy_name": {
                    "schema": {"type": "string"},
                    "required": False,
                            "model": {"expose": False},
                }
            },
            "runtime_config": {},
        },
    )
    snapshot = {
        "provider": "custom",
        "model": "frozen-model",
        "session_mode": "stateful",
        "external_context_contract": None,
        "runtime_config": {},
    }

    runtime = FrozenSnapshotStructuredOutputRuntime.__new__(
        FrozenSnapshotStructuredOutputRuntime
    )
    runtime._apply_snapshot_override(agent, snapshot)

    assert "external_context_contract" not in agent.settings



@pytest.mark.asyncio
async def test_deferred_network_finalize_builds_execution_timeline(monkeypatch) -> None:
    trace_id = uuid4()
    call_id = str(uuid4())

    async def fake_finalize(self, *_args, **_kwargs):
        return AskOutput(
            answer="done",
            trace_id=trace_id,
            usage=UsageInfo(
                input_tokens=4,
                output_tokens=3,
                total_tokens=7,
                cost_usd=0.002,
            ),
        )

    monkeypatch.setattr(
        TransactionBoundedStructuredOutputRuntime,
        "_finalize",
        fake_finalize,
    )
    monkeypatch.setattr(
        runtime_module,
        "build_deferred_agent_metrics",
        lambda _context, _output: SimpleNamespace(
            usage={
                "input_tokens": 4,
                "output_tokens": 3,
                "total_tokens": 7,
                "cost_usd": 0.002,
            },
            diagnostics={
                "schema_version": 5,
                "agent_runtime_latency_ms": 250,
                "llm_call_count": 1,
                "tool_call_count": 0,
            },
            llm_calls=[{"call_id": call_id, "latency_ms": 200}],
            started_at="2026-09-21T12:00:00+00:00",
            completed_at="2026-09-21T12:00:00.250000+00:00",
            total_latency_ms=250,
        ),
    )

    context = new_execution_context(
        request_received_at="2026-09-21T12:00:00+00:00"
    )
    setattr(context, "defer_persistence", True)
    context.trace_id = trace_id
    context.prepare_started_at = "2026-09-21T12:00:00+00:00"
    context.prepare_ended_at = "2026-09-21T12:00:00.010000+00:00"
    context.prepare_latency_ms = 10
    context.execution = InstrumentedExecution(
        result=None,
        timeline=[
            {
                "kind": "llm",
                "payload": {
                    "call_id": call_id,
                    "call_index": 1,
                    "phase": "response_generation",
                    "status": "success",
                    "started_at": "2026-09-21T12:00:00.020000+00:00",
                    "ended_at": "2026-09-21T12:00:00.220000+00:00",
                    "latency_ms": 200,
                    "provider": "custom",
                    "model": "deepseek-v4-flash",
                },
            }
        ],
    )

    runtime = FrozenSnapshotStructuredOutputRuntime.__new__(
        FrozenSnapshotStructuredOutputRuntime
    )
    token = current_execution.set(context)
    try:
        output = await runtime._finalize(
            None,
            None,
            None,
            trace_id,
            "done",
            UsageInfo(
                input_tokens=4,
                output_tokens=3,
                total_tokens=7,
                cost_usd=0.002,
            ),
            "deepseek-v4-flash",
            "custom",
            200,
            [],
            None,
            None,
            [],
            False,
            None,
            None,
        )
    finally:
        current_execution.reset(token)

    event_types = {event["event_type"] for event in output.execution_events}
    assert {
        "agent.execution.started",
        "agent.prepare.started",
        "agent.prepare.completed",
        "llm.call.started",
        "llm.call.completed",
        "structured_output.parse.completed",
        "agent.execution.completed",
    } <= event_types
    assert "http.request.received" not in event_types
    assert output.diagnostics["agent_runtime_latency_ms"] == 250
