from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyRequest
from modules.agent.infra.execution.strategies.scientific_method import (
    ScientificMethodExecutionStrategy,
)
from modules.agent.infra.execution.strategy_runtime.runner import execute_strategy


class _SimulatedCrash(RuntimeError):
    pass


class _SequenceModel:
    def __init__(self) -> None:
        self.responses = [
            AIMessage(content="Question framed from observations."),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "experiment-1",
                        "name": "lookup",
                        "args": {"id": "123"},
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Evidence collected. I will analyze it next."),
            AIMessage(content="The experiment supports the primary hypothesis."),
            AIMessage(content="Critical review found no material contradiction."),
            AIMessage(content="Conclusion supported by the collected evidence."),
        ]
        self.invocation_count = 0
        self.invocations: list[list] = []

    def bind_tools(self, _tools, *, tool_choice):
        assert tool_choice == "auto"
        return self

    async def ainvoke(self, messages):
        self.invocations.append(list(messages))
        response = self.responses[self.invocation_count]
        self.invocation_count += 1
        return response


class _Factory:
    def __init__(self, model) -> None:
        self.model = model

    def create_chat_model(self, **_kwargs):
        return self.model


def _request(model, execute_single_tool) -> ExecutionStrategyRequest:
    return ExecutionStrategyRequest(
        llm_factory=_Factory(model),
        execute_single_tool=execute_single_tool,
        clean_json_answer=lambda value: value,
        agent=SimpleNamespace(
            provider="openai",
            model="test-model",
            temperature=0.2,
            max_output_tokens=512,
            settings={"runtime_config": {"execution_strategy": "scientific_method"}},
        ),  # type: ignore[arg-type]
        api_key="secret",
        base_url=None,
        response_format={},
        json_enabled=False,
        has_tools=True,
        agent_tools=[
            {
                "type": "function",
                "function": {
                    "name": "lookup",
                    "description": "Lookup evidence",
                    "parameters": {"type": "object"},
                },
            }
        ],
        tool_name_to_id={"lookup": "tool-id"},
        messages=[],
        context_assembler=None,
    )


async def _execute(request: ExecutionStrategyRequest):
    return await execute_strategy(ScientificMethodExecutionStrategy(), request)


def _directive_phase(messages: list) -> str | None:
    for message in messages:
        metadata = getattr(message, "additional_kwargs", {}).get("woobe_context", {})
        if metadata.get("kind") == "execution_directive":
            return metadata.get("phase")
    return None


@pytest.mark.asyncio
async def test_scientific_method_resumes_after_experiment_without_replaying_tool() -> None:
    model = _SequenceModel()
    tool_calls = 0
    captured: dict = {}

    async def execute_single_tool(_tool_call, resolved_tool_id):
        nonlocal tool_calls
        assert resolved_tool_id == "tool-id"
        tool_calls += 1
        return {
            "success": True,
            "output": {"result": {"active": True}},
            "duration_ms": 1,
            "error": None,
        }

    class CrashAfterCheckpointRecorder:
        async def emit(self, event_type, payload=None, *, durable=False):
            captured.setdefault("events", []).append(
                {
                    "event_type": event_type,
                    "payload": dict(payload or {}),
                    "durable": durable,
                }
            )

        async def checkpoint(self, state, *, durable=True):
            captured["state"] = state
            captured["durable"] = durable
            raise _SimulatedCrash("process stopped after scientific experiment")

    first_context = new_execution_context()
    first_context.run_event_recorder = CrashAfterCheckpointRecorder()
    first_token = current_execution.set(first_context)
    try:
        with pytest.raises(_SimulatedCrash):
            await _execute(_request(model, execute_single_tool))
    finally:
        current_execution.reset(first_token)

    assert captured["durable"] is True
    assert captured["events"] == [
        {
            "event_type": "assistant.message.completed",
            "payload": {
                "message_id": captured["events"][0]["payload"]["message_id"],
                "content": "Evidence collected. I will analyze it next.",
                "phase": "experiment_update_1",
                "output_mode": "intermediate",
                "provider": "openai",
                "model": "test-model",
                "partial": False,
                "completed_at": captured["events"][0]["payload"]["completed_at"],
            },
            "durable": True,
        }
    ]
    assert captured["state"]["resume_policy"] == "continue_execution_strategy"
    assert captured["state"]["execution_strategy"] == "scientific_method"
    assert captured["state"]["strategy_cursor"]["state"] == {
        "phase": "evidence_analysis_1",
        "experiment_round": 1,
        "after_evidence_phase": "critical_review",
        "stop_reason": None,
    }
    assert captured["state"]["strategy_cursor"]["next_call_index"] == 4
    assert model.invocation_count == 3
    assert tool_calls == 1

    second_context = new_execution_context()
    second_context.resume_state = captured["state"]
    second_token = current_execution.set(second_context)
    try:
        execution = await _execute(_request(model, execute_single_tool))
    finally:
        current_execution.reset(second_token)

    assert model.invocation_count == 6
    assert tool_calls == 1
    assert execution.result.content == "Conclusion supported by the collected evidence."
    assert len(execution.tool_calls) == 1
    assert len(execution.llm_calls) == 6
    assert second_context.resume_state is None
    assert _directive_phase(model.invocations[3]) == "evidence_analysis_1"
    assert any(isinstance(message, AIMessage) for message in model.invocations[3])
    assert any(isinstance(message, ToolMessage) for message in model.invocations[3])
    assert any(
        isinstance(message, AIMessage)
        and message.content == "Evidence collected. I will analyze it next."
        for message in model.invocations[3]
    )
