from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyRequest
from modules.agent.infra.execution.strategies.standard import StandardExecutionStrategy


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


class _RecordingFactory:
    def __init__(self, model: Any) -> None:
        self.model = model
        self.calls: list[dict[str, Any]] = []

    def create_chat_model(self, **kwargs):
        self.calls.append(kwargs)
        return self.model


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
    factory: _RecordingFactory,
    execute_single_tool,
    has_tools: bool,
    agent_tools: list[dict] | None = None,
    tool_name_to_id: dict[str, str] | None = None,
) -> ExecutionStrategyRequest:
    return ExecutionStrategyRequest(
        llm_factory=factory,
        execute_single_tool=execute_single_tool,
        clean_json_answer=lambda value: value,
        agent=_agent(),
        api_key="test-key",
        base_url=None,
        response_format={},
        json_enabled=False,
        has_tools=has_tools,
        agent_tools=agent_tools or [],
        tool_name_to_id=tool_name_to_id or {},
        messages=[],
        context_assembler=None,
    )


@pytest.mark.asyncio
async def test_standard_strategy_preserves_single_model_execution_without_tools() -> None:
    model = _SequenceModel([AIMessage(content="direct answer")])
    factory = _RecordingFactory(model)

    async def execute_single_tool(_tool_call, _tool_id):
        raise AssertionError("Tool execution must not run")

    execution = await StandardExecutionStrategy().execute(
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

    execution = await StandardExecutionStrategy().execute(
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
