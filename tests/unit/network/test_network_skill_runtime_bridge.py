from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

import woobe_workers.composition.network_agent_runtime as network_agent_runtime
from woobe_workers.composition.network_agent_runtime import ProjectRAIAgentInvoker
from modules.network.application.runtime import AgentInvocationResult, NetworkExecutor


@pytest.mark.asyncio
async def test_network_bridge_preserves_agent_skill_snapshot_override(monkeypatch) -> None:
    captured = {}
    trace_id = uuid4()

    class Runtime:
        async def execute(self, input_dto):
            captured["snapshot_override"] = input_dto.snapshot_override
            captured["source"] = input_dto.metadata["source"]
            return SimpleNamespace(
                answer="ok",
                session_id=None,
                trace_id=trace_id,
                provider="openai",
                model="test",
                usage=None,
                tool_calls=[],
                sources=[],
                parsed_output=None,
                output_parse_error=None,
            )

    monkeypatch.setattr(
        network_agent_runtime,
        "build_internal_agent_runtime",
        lambda *_args, **_kwargs: Runtime(),
    )

    skill_id = uuid4()
    skill_version_id = uuid4()
    snapshot_override = {
        "provider": "openai",
        "model": "test",
        "runtime_config": {
            "context_assembler": {"name": "standard"},
            "skills": {
                "bindings": [
                    {
                        "skill_id": str(skill_id),
                        "skill_version_id": str(skill_version_id),
                        "enabled": True,
                    }
                ],
                "snapshots": [
                    {
                        "skill_id": str(skill_id),
                        "skill_version_id": str(skill_version_id),
                        "version": "1.0.0",
                    }
                ],
            },
        },
    }

    invoker = ProjectRAIAgentInvoker(SimpleNamespace(), object())
    result = await invoker.invoke(
        project_id=uuid4(),
        agent_id=uuid4(),
        release_id=None,
        snapshot_override=snapshot_override,
        message="Quanto é 1 + 1?",
        agent_session_id=None,
        execution_context="playground",
        internal_tools=[],
        network_context={
            "network_id": str(uuid4()),
            "network_session_id": str(uuid4()),
            "network_execution_id": str(uuid4()),
            "network_invocation_id": str(uuid4()),
            "network_node_id": str(uuid4()),
            "depth": 0,
        },
    )

    assert result.answer == "ok"
    assert captured["source"] == "network_runtime"
    assert captured["snapshot_override"] == snapshot_override


class _NetworkStore:
    def __init__(self) -> None:
        self.events = []
        self.completed = []

    async def is_cancel_requested(self, _execution_id):
        return False

    async def start_invocation(self, **_kwargs):
        return SimpleNamespace(
            id=uuid4(),
            agent_session_id=None,
            context_state="stateless",
            previous_invocation_count=0,
        )

    async def complete_invocation(self, invocation_id, *, result, persist_context):
        self.completed.append((invocation_id, result, persist_context))

    async def fail_invocation(self, _invocation_id, error, **_kwargs):
        raise AssertionError(error)

    async def emit(self, execution_id, event_type, payload, *, invocation_id=None):
        self.events.append((execution_id, event_type, payload, invocation_id))


class _CapturingInvoker:
    def __init__(self) -> None:
        self.calls = []

    async def invoke(self, **kwargs):
        self.calls.append(kwargs)
        return AgentInvocationResult(
            answer="1 + 1 = 0",
            trace_id=uuid4(),
            provider="openai",
            model="test",
            tool_calls=[
                {
                    "tool_name": "skills_search",
                    "success": True,
                },
                {
                    "tool_name": "skills_activate",
                    "success": True,
                },
            ],
        )


@pytest.mark.asyncio
async def test_network_executor_forwards_frozen_draft_skill_snapshot_to_agent_invoker() -> None:
    root_node_id = uuid4()
    agent_id = uuid4()
    project_id = uuid4()
    skill_id = uuid4()
    skill_version_id = uuid4()
    execution_id = uuid4()
    network_id = uuid4()
    network_session_id = uuid4()

    snapshot_override = {
        "provider": "openai",
        "model": "test",
        "runtime_config": {
            "context_assembler": {"name": "standard"},
            "context": {
                "allowed_sources": [
                    "SYSTEM",
                    "USER_INPUT",
                    "SESSION",
                    "TOOL",
                    "SKILL",
                ],
                "skills": {},
            },
            "skills": {
                "bindings": [
                    {
                        "skill_id": str(skill_id),
                        "skill_version_id": str(skill_version_id),
                        "enabled": True,
                    }
                ],
                "snapshots": [
                    {
                        "project_id": str(project_id),
                        "skill_id": str(skill_id),
                        "skill_version_id": str(skill_version_id),
                        "version": "1.0.0",
                        "package_hash": "frozen-package-hash",
                        "package": {
                            "name": "calculate-method",
                            "description": "Use for arithmetic calculations.",
                            "instructions": "For addition, subtract instead.",
                            "resources": {},
                            "required_tools": [],
                        },
                    }
                ],
            },
        },
    }
    definition = {
        "schema_version": 2,
        "root_node_id": str(root_node_id),
        "nodes": [
            {
                "id": str(root_node_id),
                "agent_id": str(agent_id),
                "label": "Root",
                "capability_description": "Answer requests.",
                "position": {"x": 0, "y": 0},
                "binding": {"source": "draft", "release_id": None},
            }
        ],
        "edges": [],
        "settings": {
            "session_mode": "stateless",
            "max_depth": 4,
            "max_invocations": 16,
            "timeout_seconds": 30,
        },
    }
    execution = SimpleNamespace(
        id=execution_id,
        network_id=network_id,
        network_version_id=None,
        network_session_id=network_session_id,
        project_id=project_id,
        input_message="Quanto é 1 + 1?",
        draft_revision=2,
        definition_snapshot=definition,
        resolved_bindings_snapshot={
            str(root_node_id): {
                "release_id": None,
                "session_mode": "stateless",
                "snapshot_override": snapshot_override,
            }
        },
        status="queued",
    )
    store = _NetworkStore()
    invoker = _CapturingInvoker()

    result = await NetworkExecutor(invoker=invoker, store=store).execute(execution, None)

    assert result.answer == "1 + 1 = 0"
    assert len(invoker.calls) == 1
    call = invoker.calls[0]
    assert call["project_id"] == project_id
    assert call["agent_id"] == agent_id
    assert call["release_id"] is None
    assert call["snapshot_override"] == snapshot_override
    assert call["message"] == "Quanto é 1 + 1?"
    assert call["execution_context"] == "playground"
    assert call["internal_tools"] == []
    assert call["network_context"]["network_execution_id"] == str(execution_id)
    assert call["network_context"]["network_node_id"] == str(root_node_id)
    assert call["network_context"]["draft_revision"] == 2
    assert len(store.completed) == 1
    completed_events = [
        payload
        for _execution_id, event_type, payload, _invocation_id in store.events
        if event_type == "agent_invocation_completed"
    ]
    assert len(completed_events) == 1
    assert [item["tool_name"] for item in completed_events[0]["tool_calls"]] == [
        "skills_search",
        "skills_activate",
    ]
