from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from modules.agent.application.context_managers.standard import StandardContextManager
from modules.agent.application.dtos.runtime_dtos import SourceInfo

from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyRequest
from modules.agent.infra.execution.strategies.standard import StandardExecutionStrategy
from modules.agent.infra.execution.strategy_runtime.runner import execute_strategy


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


def _request(
    model,
    execute_single_tool,
    *,
    knowledge_retrieve=None,
    knowledge_query: str | None = None,
) -> ExecutionStrategyRequest:
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
        messages=(
            [HumanMessage(content=knowledge_query)]
            if knowledge_query
            else []
        ),
        context_assembler=StandardContextManager(),
        knowledge_retrieve=knowledge_retrieve,
        knowledge_query=knowledge_query,
    )


async def _execute(request: ExecutionStrategyRequest):
    return await execute_strategy(StandardExecutionStrategy(), request)


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
        async def emit(self, _event_type, _payload):
            return None

        async def checkpoint(self, state, *, durable=True):
            captured["state"] = state
            captured["durable"] = durable
            raise _SimulatedCrash("process stopped after durable Tool boundary")

    first_context = new_execution_context()
    first_context.run_id = uuid4()
    first_context.project_id = uuid4()
    first_context.run_event_recorder = CrashAfterCheckpointRecorder()
    first_token = current_execution.set(first_context)
    try:
        with pytest.raises(_SimulatedCrash):
            await _execute(_request(model, execute_single_tool))
    finally:
        current_execution.reset(first_token)

    assert captured["durable"] is True
    assert captured["state"]["resume_policy"] == "continue_execution_strategy"
    assert captured["state"]["execution_strategy"] == "standard"
    assert captured["state"]["strategy_cursor"]["state"] == {
        "phase": "tool_followup_1",
        "tool_round": 1,
        "consecutive_failures": 0,
        "knowledge_resolved": True,
        "preflight_resolved": True,
        "stop_reason": None,
    }
    assert captured["state"]["strategy_cursor"]["next_call_index"] == 2
    assert model.invocation_count == 1
    assert tool_calls == 1

    second_context = new_execution_context()
    second_context.run_id = uuid4()
    second_context.project_id = uuid4()
    second_context.resume_state = captured["state"]
    second_token = current_execution.set(second_context)
    try:
        execution = await _execute(_request(model, execute_single_tool))
    finally:
        current_execution.reset(second_token)

    assert model.invocation_count == 2
    assert tool_calls == 1
    assert execution.result.content == "Customer 123 is active."
    assert len(execution.tool_calls) == 1
    assert len(execution.llm_calls) == 2
    assert second_context.resume_state is None
    assert any(isinstance(message, AIMessage) for message in model.invocations[1])
    assert any(isinstance(message, ToolMessage) for message in model.invocations[1])


@pytest.mark.asyncio
async def test_standard_strategy_restores_knowledge_contribution_without_retrieval_replay() -> None:
    model = _SequenceModel()
    tool_calls = 0
    knowledge_calls = 0
    captured: dict = {}

    async def retrieve_knowledge(query: str):
        nonlocal knowledge_calls
        assert query == "customer 123"
        knowledge_calls += 1
        return SimpleNamespace(
            context="Customer records are authoritative.",
            sources=(
                SourceInfo(
                    document_id="doc-1",
                    chunk_id="chunk-1",
                    score=0.99,
                ),
            ),
            metrics={"retrieved_chunks": 1},
        )

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
        async def emit(self, _event_type, _payload):
            return None

        async def checkpoint(self, state, *, durable=True):
            captured["state"] = state
            captured["durable"] = durable
            raise _SimulatedCrash("process stopped after durable Tool boundary")

    request = _request(
        model,
        execute_single_tool,
        knowledge_retrieve=retrieve_knowledge,
        knowledge_query="customer 123",
    )

    first_context = new_execution_context()
    first_context.run_id = uuid4()
    first_context.project_id = uuid4()
    first_context.run_event_recorder = CrashAfterCheckpointRecorder()
    first_token = current_execution.set(first_context)
    try:
        with pytest.raises(_SimulatedCrash):
            await _execute(request)
    finally:
        current_execution.reset(first_token)

    assert knowledge_calls == 1
    assert tool_calls == 1
    assert captured["durable"] is True
    contribution = captured["state"]["context_contributions"]["knowledge.primary"]
    assert contribution["source_type"] == "KNOWLEDGE"
    assert contribution["content"] == "Customer records are authoritative."
    assert contribution["metadata"]["sources"][0]["document_id"] == "doc-1"
    assert captured["state"]["strategy_cursor"]["state"]["knowledge_resolved"] is True

    second_context = new_execution_context()
    second_context.run_id = uuid4()
    second_context.project_id = uuid4()
    second_context.resume_state = captured["state"]
    second_token = current_execution.set(second_context)
    try:
        execution = await _execute(request)
    finally:
        current_execution.reset(second_token)

    assert knowledge_calls == 1
    assert tool_calls == 1
    assert len(execution.knowledge_calls) == 1
    assert len(execution.sources) == 1
    assert execution.sources[0].document_id == "doc-1"
    assert "Customer records are authoritative." in str(model.invocations[1])
    assert execution.result.content == "Customer 123 is active."
