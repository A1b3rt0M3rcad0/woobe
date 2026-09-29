from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from modules.agent.application.context_managers.standard import StandardContextManager
from modules.agent.application.dtos.runtime_dtos import SourceInfo
from modules.agent.application.interfaces.execution import InstrumentedExecutionError
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyRequest
from modules.agent.application.knowledge_strategy_registry import build_knowledge_strategy_registry
from modules.agent.infra.execution.strategies.standard import StandardExecutionStrategy
from modules.agent.infra.execution.strategy_runtime.runner import execute_strategy


class _SequenceModel:
    def __init__(self, responses: list[AIMessage]) -> None:
        self.responses = responses
        self.invocation_count = 0
        self.invocations: list[list[Any]] = []

    def bind_tools(self, _tools, *, tool_choice):
        assert tool_choice == "auto"
        return self

    async def ainvoke(self, _messages):
        self.invocations.append(list(_messages))
        response = self.responses[self.invocation_count]
        self.invocation_count += 1
        return response


class _FailingModel:
    async def ainvoke(self, _messages):
        raise RuntimeError("provider down")


class _RecordingFactory:
    def __init__(self, model: Any) -> None:
        self.model = model
        self.calls: list[dict[str, Any]] = []

    def create_chat_model(self, **kwargs):
        self.calls.append(kwargs)
        return self.model


class _MultiModelFactory:
    def __init__(self, models: list[Any]) -> None:
        self.models = models
        self.calls: list[dict[str, Any]] = []

    def create_chat_model(self, **kwargs):
        self.calls.append(kwargs)
        return self.models[len(self.calls) - 1]


def _agent():
    return SimpleNamespace(
        provider="openrouter",
        model="deepseek/deepseek-v4-flash",
        temperature=0.2,
        max_output_tokens=1000,
        settings={},
    )


def _request(
    *,
    factory: Any,
    execute_single_tool,
    has_tools: bool,
    agent_tools: list[dict] | None = None,
    tool_name_to_id: dict[str, str] | None = None,
    json_enabled: bool = False,
    response_format: dict | None = None,
    knowledge_retrieve=None,
    agent: Any | None = None,
    messages: list[Any] | None = None,
) -> ExecutionStrategyRequest:
    return ExecutionStrategyRequest(
        llm_factory=factory,
        execute_single_tool=execute_single_tool,
        clean_json_answer=lambda value: value,
        agent=agent or _agent(),
        api_key="test-key",
        base_url=None,
        response_format=response_format or {},
        json_enabled=json_enabled,
        has_tools=has_tools,
        agent_tools=agent_tools or [],
        tool_name_to_id=tool_name_to_id or {},
        messages=list(messages or []),
        context_assembler=StandardContextManager(),
        knowledge_retrieve=knowledge_retrieve,
        knowledge_strategy=build_knowledge_strategy_registry().resolve("rag"),
    )


async def _execute(request: ExecutionStrategyRequest):
    existing = current_execution.get()
    if existing is not None:
        return await execute_strategy(StandardExecutionStrategy(), request)

    context = new_execution_context()
    context.run_id = uuid4()
    context.project_id = uuid4()
    token = current_execution.set(context)
    try:
        return await execute_strategy(StandardExecutionStrategy(), request)
    finally:
        current_execution.reset(token)


@pytest.mark.asyncio
async def test_standard_strategy_preserves_single_model_execution_without_tools() -> None:
    model = _SequenceModel([AIMessage(content="direct answer")])
    factory = _RecordingFactory(model)

    async def execute_single_tool(_tool_call, _tool_id):
        raise AssertionError("Tool execution must not run")

    execution = await _execute(
        _request(
            factory=factory,
            execute_single_tool=execute_single_tool,
            has_tools=False,
        )
    )

    assert len(factory.calls) == 1
    assert model.invocation_count == 1
    assert execution.result.content == "direct answer"
    assert execution.tool_calls == []
    assert [call["phase"] for call in execution.llm_calls] == ["response_generation"]


@pytest.mark.asyncio
async def test_standard_strategy_preserves_model_tool_model_execution() -> None:
    model = _SequenceModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "sum",
                        "args": {"a": 8, "b": 8},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="16"),
        ]
    )
    factory = _RecordingFactory(model)
    executed: list[str] = []

    async def execute_single_tool(_tool_call, resolved_tool_id):
        executed.append(resolved_tool_id)
        return {
            "success": True,
            "output": {
                "body": {"result": "16", "error": None},
                "status_code": 200,
            },
            "duration_ms": 1,
            "error": None,
        }

    execution = await _execute(
        _request(
            factory=factory,
            execute_single_tool=execute_single_tool,
            has_tools=True,
            agent_tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "sum",
                        "description": "Sum two integers",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "a": {"type": "integer"},
                                "b": {"type": "integer"},
                            },
                            "required": ["a", "b"],
                        },
                    },
                }
            ],
            tool_name_to_id={"sum": "tool-id"},
        )
    )

    assert len(factory.calls) == 1
    assert model.invocation_count == 2
    assert executed == ["tool-id"]
    assert execution.result.content == "16"
    assert len(execution.tool_calls) == 1
    assert execution.tool_calls[0].success is True
    assert [call["phase"] for call in execution.llm_calls] == [
        "capability_response_generation",
        "tool_followup_1",
    ]


@pytest.mark.asyncio
async def test_standard_strategy_preserves_valid_structured_json_without_repair() -> None:
    model = _SequenceModel([AIMessage(content='{"ok": true}')])
    factory = _RecordingFactory(model)

    async def execute_single_tool(_tool_call, _tool_id):
        raise AssertionError("Tool execution must not run")

    execution = await _execute(
        _request(
            factory=factory,
            execute_single_tool=execute_single_tool,
            has_tools=False,
            json_enabled=True,
            response_format={
                "type": "json",
                "schema": {
                    "type": "object",
                    "properties": {"ok": {"type": "boolean"}},
                    "required": ["ok"],
                },
            },
        )
    )

    assert execution.result.content == '{"ok": true}'
    assert [call["phase"] for call in execution.llm_calls] == ["response_generation"]
    assert len(factory.calls) == 1
    assert factory.calls[0]["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_standard_strategy_preserves_structured_json_repair() -> None:
    primary = _SequenceModel([AIMessage(content="not-json")])
    repair = _SequenceModel([AIMessage(content='{"ok": true}')])
    factory = _MultiModelFactory([primary, repair])

    async def execute_single_tool(_tool_call, _tool_id):
        raise AssertionError("Tool execution must not run")

    execution = await _execute(
        _request(
            factory=factory,
            execute_single_tool=execute_single_tool,
            has_tools=False,
            json_enabled=True,
            response_format={
                "type": "json",
                "schema": {
                    "type": "object",
                    "properties": {"ok": {"type": "boolean"}},
                    "required": ["ok"],
                },
            },
        )
    )

    assert execution.result.content == '{"ok": true}'
    assert [call["phase"] for call in execution.llm_calls] == [
        "response_generation",
        "json_repair",
    ]
    assert len(factory.calls) == 2
    assert factory.calls[1]["temperature"] == 0.0
    assert factory.calls[1]["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_standard_strategy_decides_fallback_through_model_capability() -> None:
    primary = _FailingModel()
    fallback = _SequenceModel([AIMessage(content="fallback answer")])
    factory = _MultiModelFactory([primary, fallback])
    agent = SimpleNamespace(
        provider="openrouter",
        model="primary-model",
        fallback_provider="openai",
        fallback_model="fallback-model",
        fallback_credential_id="fallback-credential",
        fallback_provider_model_id=None,
        temperature=0.2,
        max_output_tokens=1000,
        settings={},
    )

    async def execute_single_tool(_tool_call, _tool_id):
        raise AssertionError("Tool execution must not run")

    context = new_execution_context()
    context.prepared_fallback = {
        "api_key": "fallback-key",
        "base_url": None,
    }
    token = current_execution.set(context)
    try:
        execution = await _execute(
            _request(
                factory=factory,
                execute_single_tool=execute_single_tool,
                has_tools=False,
                agent=agent,
            )
        )
    finally:
        current_execution.reset(token)

    assert execution.result.content == "fallback answer"
    assert execution.fallback_used is True
    assert execution.fallback_info is not None
    assert execution.fallback_info["primary_error"] == "provider down"
    assert execution.fallback_info["fallback_provider"] == "openai"
    assert [call["phase"] for call in execution.llm_calls] == [
        "response_generation",
        "fallback_response_generation",
    ]
    assert len(factory.calls) == 2
    assert factory.calls[1]["provider"] == "openai"
    assert factory.calls[1]["model"] == "fallback-model"


@pytest.mark.asyncio
async def test_standard_strategy_preserves_model_failure_instrumentation() -> None:
    factory = _RecordingFactory(_FailingModel())

    async def execute_single_tool(_tool_call, _tool_id):
        raise AssertionError("Tool execution must not run")

    with pytest.raises(InstrumentedExecutionError, match="provider down") as error:
        await _execute(
            _request(
                factory=factory,
                execute_single_tool=execute_single_tool,
                has_tools=False,
            )
        )

    assert len(error.value.llm_calls) == 1
    assert error.value.llm_calls[0]["phase"] == "response_generation"
    assert error.value.failure_context["provider"] == "openrouter"
    assert error.value.failure_context["model"] == "deepseek/deepseek-v4-flash"


@pytest.mark.asyncio
async def test_standard_strategy_preserves_failed_tool_evidence() -> None:
    model = _SequenceModel(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup",
                        "args": {"id": "missing"},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="I need a valid identifier."),
        ]
    )
    factory = _RecordingFactory(model)

    async def execute_single_tool(_tool_call, _resolved_tool_id):
        return {
            "success": False,
            "output": {"body": {"error": "not found"}, "status_code": 404},
            "duration_ms": 1,
            "error": "not found",
            "error_code": "not_found",
        }

    execution = await _execute(
        _request(
            factory=factory,
            execute_single_tool=execute_single_tool,
            has_tools=True,
            agent_tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "lookup",
                        "description": "Lookup an identifier",
                        "parameters": {"type": "object"},
                    },
                }
            ],
            tool_name_to_id={"lookup": "tool-id"},
        )
    )

    assert execution.result.content == "I need a valid identifier."
    assert len(execution.tool_calls) == 1
    assert execution.tool_calls[0].success is False
    assert execution.tool_calls[0].error_code == "not_found"
    assert [call["phase"] for call in execution.llm_calls] == [
        "capability_response_generation",
        "tool_followup_1",
    ]


@pytest.mark.asyncio
async def test_standard_strategy_retrieves_knowledge_and_materializes_it_in_context_once() -> None:
    model = _SequenceModel([AIMessage(content="grounded answer")])
    factory = _RecordingFactory(model)
    retrievals: list[str] = []

    async def retrieve_knowledge(query: str):
        retrievals.append(query)
        return SimpleNamespace(
            context="Woobe runtime knowledge",
            sources=(
                SourceInfo(
                    document_id="doc-1",
                    chunk_id="chunk-1",
                    score=0.93,
                ),
            ),
            metrics={"retrieved_chunks": 1},
        )

    async def execute_single_tool(_tool_call, _tool_id):
        raise AssertionError("Tool execution must not run")

    execution = await _execute(
        _request(
            factory=factory,
            execute_single_tool=execute_single_tool,
            has_tools=False,
            knowledge_retrieve=retrieve_knowledge,
            messages=[HumanMessage(content="How does Woobe execute agents?")],
        )
    )

    assert retrievals == ["How does Woobe execute agents?"]
    assert len(execution.knowledge_calls) == 1
    assert execution.knowledge_calls[0]["found"] is True
    assert len(execution.sources) == 1
    assert execution.sources[0].document_id == "doc-1"
    assert [item["kind"] for item in execution.timeline] == ["knowledge", "llm"]

    serialized = str(model.invocations[0])
    assert "Woobe runtime knowledge" in serialized
    assert "source_type" in serialized
    assert "KNOWLEDGE" in serialized


@pytest.mark.asyncio
async def test_standard_delegates_conversation_query_to_knowledge() -> None:
    model = _SequenceModel([AIMessage(content="grounded answer")])
    factory = _RecordingFactory(model)
    retrievals: list[str] = []

    async def retrieve_knowledge(query: str):
        retrievals.append(query)
        return SimpleNamespace(context=None, sources=(), metrics={})

    async def execute_single_tool(_tool_call, _tool_id):
        raise AssertionError("Tool execution must not run")

    agent = _agent()
    agent.settings = {
        "runtime_config": {
            "rag": {
                "query_mode": "conversation_context",
                "history_turns": 1,
            }
        }
    }

    await _execute(
        _request(
            factory=factory,
            execute_single_tool=execute_single_tool,
            has_tools=False,
            knowledge_retrieve=retrieve_knowledge,
            agent=agent,
            messages=[
                HumanMessage(content="What is Woobe?"),
                AIMessage(content="It is an agentic runtime."),
                HumanMessage(content="How does execution work?"),
            ],
        )
    )

    assert retrievals == [
        "User: What is Woobe?\n"
        "Assistant: It is an agentic runtime.\n"
        "Current user message: How does execution work?"
    ]
