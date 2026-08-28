from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from modules.agent.infra.execution.instrumented_execution_runner import (
    run_instrumented_execution,
)


class SequenceToolModel:
    def __init__(self) -> None:
        self.responses = [
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
        self.invocation_count = 0

    def bind_tools(self, _tools, *, tool_choice):
        assert tool_choice == "auto"
        return self

    async def ainvoke(self, _messages):
        response = self.responses[self.invocation_count]
        self.invocation_count += 1
        return response


class NoToolDecisionModel:
    def __init__(self) -> None:
        self.responses = [AIMessage(content="Hello from the first response")]
        self.invocation_count = 0

    def bind_tools(self, _tools, *, tool_choice):
        assert tool_choice == "auto"
        return self

    async def ainvoke(self, _messages):
        response = self.responses[self.invocation_count]
        self.invocation_count += 1
        return response


class RecordingLlmFactory:
    def __init__(self, model: Any) -> None:
        self.model = model
        self.create_count = 0

    def create_chat_model(self, **_kwargs):
        self.create_count += 1
        return self.model


def _agent():
    return SimpleNamespace(
        provider="openrouter",
        model="deepseek/deepseek-v4-flash",
        temperature=0.2,
        max_output_tokens=1000,
        settings={},
    )


def _agent_tools():
    return [
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
    ]


@pytest.mark.asyncio
async def test_text_tool_execution_only_invokes_again_after_tool_call() -> None:
    model = SequenceToolModel()
    factory = RecordingLlmFactory(model)

    async def execute_single_tool(_tool_call, resolved_tool_id):
        assert resolved_tool_id == "tool-id"
        return {
            "success": True,
            "output": {
                "body": {"result": "16", "error": None},
                "status_code": 200,
            },
            "duration_ms": 1,
            "error": None,
        }

    execution = await run_instrumented_execution(
        llm_factory=factory,
        execute_single_tool=execute_single_tool,
        clean_json_answer=lambda value: value,
        agent=_agent(),
        api_key="test-key",
        base_url=None,
        response_format={},
        json_enabled=False,
        has_tools=True,
        agent_tools=_agent_tools(),
        tool_name_to_id={"sum": "tool-id"},
        messages=[],
    )

    assert factory.create_count == 1
    assert model.invocation_count == 2
    assert [call["phase"] for call in execution.llm_calls] == [
        "capability_response_generation",
        "tool_followup_1",
    ]
    assert execution.result.content == "16"
    assert len(execution.tool_calls) == 1
    assert execution.tool_calls[0].success is True


@pytest.mark.asyncio
async def test_text_agent_with_tools_finishes_in_first_model_call_without_tool_call() -> None:
    model = NoToolDecisionModel()
    factory = RecordingLlmFactory(model)

    async def execute_single_tool(_tool_call, _resolved_tool_id):
        raise AssertionError("No Tool should be executed")

    execution = await run_instrumented_execution(
        llm_factory=factory,
        execute_single_tool=execute_single_tool,
        clean_json_answer=lambda value: value,
        agent=_agent(),
        api_key="test-key",
        base_url=None,
        response_format={},
        json_enabled=False,
        has_tools=True,
        agent_tools=_agent_tools(),
        tool_name_to_id={"sum": "tool-id"},
        messages=[],
    )

    assert factory.create_count == 1
    assert model.invocation_count == 1
    assert [call["phase"] for call in execution.llm_calls] == [
        "capability_response_generation"
    ]
    assert execution.result.content == "Hello from the first response"
    assert execution.tool_calls == []
