from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyRequest
from modules.agent.infra.execution.strategies.standard import StandardExecutionStrategy


class _SimulatedCrash(RuntimeError):
    pass


class _SequenceModel:
    def __init__(self) -> None:
        self.responses = [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "lookup",
                        "args": {"id": "123"},
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Customer 123 is active."),
        ]
        self.invocation_count = 0

    def bind_tools(self, _tools, *, tool_choice):
        assert tool_choice == "auto"
        return self

    async def ainvoke(self, _messages):
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
            settings={"runtime_config": {"execution_strategy": "standard"}},
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
                    "description": "Lookup customer",
                    "parameters": {"type": "object"},
                },
            }
        ],
        tool_name_to_id={"lookup": "tool-id"},
        messages=[],
        context_assembler=None,
    )


@pytest.mark.asyncio
async def test_standard_strategy_resumes_generic_checkpoint_without_replaying_tool() -> None:
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
        async def checkpoint(self, state, *, durable=True):
            captured["state"] = state
            captured["durable"] = durable
            raise _SimulatedCrash("process stopped after durable Tool boundary")

    first_context = new_execution_context()
    first_context.run_event_recorder = CrashAfterCheckpointRecorder()
    first_token = current_execution.set(first_context)
    try:
        with pytest.raises(_SimulatedCrash):
            await StandardExecutionStrategy().execute(
                _request(model, execute_single_tool)
            )
    finally:
        current_execution.reset(first_token)

    assert captured["durable"] is True
    assert captured["state"]["resume_policy"] == "continue_execution_strategy"
    assert captured["state"]["execution_strategy"] == "standard"
    assert captured["state"]["strategy_cursor"]["next_phase"] == "tool_followup_1"
    assert model.invocation_count == 1
    assert tool_calls == 1

    second_context = new_execution_context()
    second_context.resume_state = captured["state"]
    second_token = current_execution.set(second_context)
    try:
        execution = await StandardExecutionStrategy().execute(
            _request(model, execute_single_tool)
        )
    finally:
        current_execution.reset(second_token)

    assert model.invocation_count == 2
    assert tool_calls == 1
    assert execution.result.content == "Customer 123 is active."
    assert len(execution.tool_calls) == 1
    assert len(execution.llm_calls) == 2
    assert second_context.resume_state is None
