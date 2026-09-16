from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from modules.agent.application.interfaces.execution import InstrumentedExecutionError
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyRequest
from modules.agent.infra.execution.strategies.standard import (
    build_standard_strategy_definition,
)
from modules.agent.infra.execution.strategy_runtime.runner import (
    execute_strategy_definition,
)


class _SequenceModel:
    def __init__(self, responses: list[AIMessage]) -> None:
        self.responses = responses
        self.invocation_count = 0

    def bind_tools(self, _tools, *, tool_choice):
        assert tool_choice == "auto"
        return self

    async def ainvoke(self, _messages):
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
) -> ExecutionStrategyRequest:
    return ExecutionStrategyRequest(
        llm_factory=factory,
        execute_single_tool=execute_single_tool,
        clean_json_answer=lambda value: value,
        agent=_agent(),
        api_key="test-key",
        base_url=None,
        response_format=response_format or {},
        json_enabled=json_enabled,
        has_tools=has_tools,
        agent_tools=agent_tools or [],
        tool_name_to_id=tool_name_to_id or {},
        messages=[],
        context_assembler=None,
    )


async def _execute(request: ExecutionStrategyRequest):
    return await execute_strategy_definition(build_standard_strategy_definition(), request)


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
